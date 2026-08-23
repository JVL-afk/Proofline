[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$AuthorizationRecordPath
)

$ErrorActionPreference = "Stop"
$InterfaceIndex = 13
$InterfaceAlias = "Wi-Fi"
$InterfaceGuid = "{997EE793-757E-4FD9-8138-CE1BF9FA1B32}"
$BeforeDns = @("192.168.1.1")
$AfterDns = @("8.8.8.8", "8.8.4.4")
$Hosts = @("data.texas.gov", "nominatim.openstreetmap.org")
$Event = "APPROVE_ELEVATED_LOCAL_DNS_RESOLVER_REMEDIATION_SUCCESSOR"
$EvidenceRelativePath = "local-data/m6.7/seed-source-connectivity/elevated-local-dns-remediation-evidence.json"

function Test-ArrayEqual {
    param([object[]]$Left, [object[]]$Right)
    if ($Left.Count -ne $Right.Count) { return $false }
    for ($index = 0; $index -lt $Left.Count; $index++) {
        if ([string]$Left[$index] -ne [string]$Right[$index]) { return $false }
    }
    return $true
}

function Get-TextSha256 {
    param([string]$Value)
    $hasher = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString(
            $hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($Value))
        )).Replace("-", "").ToLowerInvariant()
    }
    finally {
        $hasher.Dispose()
    }
}

function Get-ElevationEvidence {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    $administrator = $principal.IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
    $groups = (whoami /groups | Out-String)
    $integrityMatches = [regex]::Matches($groups, "S-1-16-(\d+)")
    $integrityRid = 0
    foreach ($match in $integrityMatches) {
        $candidate = [int]$match.Groups[1].Value
        if ($candidate -gt $integrityRid) { $integrityRid = $candidate }
    }
    return [ordered]@{
        administrator_token = $administrator
        integrity_rid = $integrityRid
        high_or_stronger_integrity = ($integrityRid -ge 12288)
        principal_sha256 = Get-TextSha256 $identity.User.Value
    }
}

function Get-LocalSnapshot {
    $adapter = Get-NetAdapter -InterfaceIndex $InterfaceIndex -ErrorAction Stop
    $ipv4Interface = Get-NetIPInterface `
        -InterfaceIndex $InterfaceIndex -AddressFamily IPv4 -ErrorAction Stop
    $ipv4Dns = @((Get-DnsClientServerAddress `
        -InterfaceIndex $InterfaceIndex -AddressFamily IPv4 -ErrorAction Stop).ServerAddresses)
    $ipv6Dns = @((Get-DnsClientServerAddress `
        -InterfaceIndex $InterfaceIndex -AddressFamily IPv6 -ErrorAction Stop).ServerAddresses)
    $ipv4Addresses = @(Get-NetIPAddress `
        -InterfaceIndex $InterfaceIndex -AddressFamily IPv4 -ErrorAction Stop |
        Where-Object { $_.AddressState -eq "Preferred" } |
        Sort-Object IPAddress | ForEach-Object { $_.IPAddress })
    $gateways = @(Get-NetRoute `
        -InterfaceIndex $InterfaceIndex -AddressFamily IPv4 `
        -DestinationPrefix "0.0.0.0/0" -ErrorAction Stop |
        Sort-Object NextHop | ForEach-Object { $_.NextHop })
    $proxy = (netsh winhttp show proxy | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw "WINHTTP_PROXY_INSPECTION_FAILED" }
    $vpn = Get-NetAdapter |
        Where-Object { $_.Name -match "Radmin|VPN" } |
        Sort-Object ifIndex |
        Select-Object Name, ifIndex, Status, InterfaceGuid |
        ConvertTo-Json -Compress
    $firewall = Get-NetFirewallProfile |
        Sort-Object Name |
        Select-Object Name, Enabled, DefaultInboundAction, DefaultOutboundAction |
        ConvertTo-Json -Compress
    return [ordered]@{
        interface_alias = $adapter.Name
        interface_index = $adapter.ifIndex
        interface_guid = "{" + $adapter.InterfaceGuid.ToString().Trim("{}").ToUpperInvariant() + "}"
        adapter_status = $adapter.Status
        ipv4_dns = $ipv4Dns
        ipv6_dns = $ipv6Dns
        ipv4_addresses = $ipv4Addresses
        gateways = $gateways
        dhcp_addressing = $ipv4Interface.Dhcp.ToString()
        proxy_state_sha256 = Get-TextSha256 $proxy
        vpn_state_sha256 = Get-TextSha256 $vpn
        firewall_state_sha256 = Get-TextSha256 $firewall
    }
}

function Assert-ActiveAdapter {
    $active = Get-NetRoute -AddressFamily IPv4 -DestinationPrefix "0.0.0.0/0" |
        Where-Object { $_.State -eq "Alive" } |
        ForEach-Object {
            $interfaceMetric = (Get-NetIPInterface `
                -InterfaceIndex $_.InterfaceIndex -AddressFamily IPv4).InterfaceMetric
            [pscustomobject]@{
                InterfaceIndex = $_.InterfaceIndex
                EffectiveMetric = [int]$_.RouteMetric + [int]$interfaceMetric
            }
        } |
        Sort-Object EffectiveMetric |
        Select-Object -First 1
    if ($null -eq $active -or $active.InterfaceIndex -ne $InterfaceIndex) {
        throw "ACTIVE_ADAPTER_MISMATCH"
    }
}

function Assert-UnchangedExceptIpv4Dns {
    param(
        [System.Collections.IDictionary]$Before,
        [System.Collections.IDictionary]$After
    )
    foreach ($field in @(
        "interface_alias", "interface_index", "interface_guid", "adapter_status",
        "dhcp_addressing", "proxy_state_sha256", "vpn_state_sha256", "firewall_state_sha256"
    )) {
        if ([string]$Before[$field] -ne [string]$After[$field]) {
            throw "UNEXPECTED_CHANGE_$($field.ToUpperInvariant())"
        }
    }
    if (-not (Test-ArrayEqual $Before.ipv4_addresses $After.ipv4_addresses)) {
        throw "IPV4_ADDRESS_CHANGED"
    }
    if (-not (Test-ArrayEqual $Before.gateways $After.gateways)) {
        throw "DEFAULT_GATEWAY_CHANGED"
    }
    if (-not (Test-ArrayEqual $Before.ipv6_dns $After.ipv6_dns)) {
        throw "IPV6_DNS_CHANGED"
    }
}

function Get-DnsProof {
    param([string]$Hostname)
    $records = @(Resolve-DnsName `
        -Name $Hostname -DnsOnly -NoHostsFile -ErrorAction Stop)
    $addresses = @($records |
        Where-Object { $_.IPAddress } |
        ForEach-Object { $_.IPAddress } |
        Sort-Object -Unique)
    if ($addresses.Count -eq 0) { throw "DNS_PROOF_NO_ADDRESS_$Hostname" }
    $families = @($addresses |
        ForEach-Object { if ($_ -match ":") { "IPv6" } else { "IPv4" } } |
        Sort-Object -Unique)
    return [ordered]@{
        hostname = $Hostname
        success = $true
        address_count = $addresses.Count
        address_families = $families
        address_set_sha256 = Get-TextSha256 ($addresses -join "`n")
        logical_system_dns_queries = 1
    }
}

function Write-Evidence {
    param(
        [System.Collections.IDictionary]$Evidence,
        [string]$RepositoryRoot
    )
    $target = Join-Path $RepositoryRoot $EvidenceRelativePath
    $directory = Split-Path -Parent $target
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
    $json = $Evidence | ConvertTo-Json -Depth 10
    [IO.File]::WriteAllText($target, $json + "`n", [Text.UTF8Encoding]::new($false))
    Write-Output $target
}

# The grant is not consumed unless every local, zero-network precondition below passes.
$elevation = Get-ElevationEvidence
if (-not $elevation.administrator_token -or -not $elevation.high_or_stronger_integrity) {
    throw "ELEVATION_PRECONDITION_FAILED_GRANT_NOT_CONSUMED"
}

$scriptPath = $MyInvocation.MyCommand.Path
$repositoryRoot = (Resolve-Path (Join-Path (Split-Path -Parent $scriptPath) "..")).Path
$authorizationPath = (Resolve-Path $AuthorizationRecordPath).Path
if (-not $authorizationPath.StartsWith($repositoryRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "AUTHORIZATION_RECORD_OUTSIDE_REPOSITORY"
}
$authorization = Get-Content -Raw $authorizationPath | ConvertFrom-Json
if ($authorization.event -ne $Event -or $authorization.state -ne "APPROVED") {
    throw "AUTHORIZATION_RECORD_INVALID"
}
if ([DateTimeOffset]::UtcNow -lt [DateTimeOffset]::Parse($authorization.validity.starts_at) -or
    [DateTimeOffset]::UtcNow -gt [DateTimeOffset]::Parse($authorization.validity.expires_at)) {
    throw "AUTHORIZATION_OUTSIDE_VALIDITY_WINDOW"
}
$scriptSha256 = (Get-FileHash -Algorithm SHA256 $scriptPath).Hash.ToLowerInvariant()
if ($authorization.exact_executable_sha256 -ne $scriptSha256) {
    throw "EXECUTABLE_HASH_MISMATCH"
}

Assert-ActiveAdapter
$before = Get-LocalSnapshot
if ($before.interface_alias -ne $InterfaceAlias -or
    $before.interface_index -ne $InterfaceIndex -or
    $before.interface_guid -ne $InterfaceGuid -or
    $before.adapter_status -ne "Up") {
    throw "ADAPTER_IDENTITY_PRECONDITION_FAILED_GRANT_NOT_CONSUMED"
}
if (-not (Test-ArrayEqual $before.ipv4_dns $BeforeDns)) {
    throw "DNS_BEFORE_STATE_PRECONDITION_FAILED_GRANT_NOT_CONSUMED"
}

# All preconditions have passed. Only now is the one-shot grant consumed.
$consumedAt = [DateTimeOffset]::UtcNow.ToString("o")
$mutationStarted = $false
try {
    $mutationStarted = $true
    netsh interface ipv4 set dnsservers name=13 source=static address=8.8.8.8 register=primary validate=no | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "PRIMARY_DNS_SET_FAILED" }
    netsh interface ipv4 add dnsservers name=13 address=8.8.4.4 index=2 validate=no | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "ALTERNATE_DNS_SET_FAILED" }
    Clear-DnsClientCache

    $after = Get-LocalSnapshot
    if (-not (Test-ArrayEqual $after.ipv4_dns $AfterDns)) {
        throw "IPV4_DNS_AFTER_STATE_MISMATCH"
    }
    Assert-UnchangedExceptIpv4Dns $before $after

    # Exactly one ordinary current-system DNS proof per frozen hostname.
    $proofs = @()
    foreach ($hostname in $Hosts) { $proofs += Get-DnsProof $hostname }

    $evidence = [ordered]@{
        record_type = "M67_ELEVATED_LOCAL_DNS_REMEDIATION_EVIDENCE"
        version = "1.0.0"
        state = "LOCAL_DNS_RESOLVER_REMEDIATION_APPLIED_SYSTEM_DNS_PROOF_PASS"
        terminal = $true
        grant_consumed = $true
        consumed_at = $consumedAt
        observed_at = [DateTimeOffset]::UtcNow.ToString("o")
        authorization_record_sha256 = (Get-FileHash -Algorithm SHA256 $authorizationPath).Hash.ToLowerInvariant()
        executable_sha256 = $scriptSha256
        elevation = $elevation
        before = $before
        after = $after
        proofs = $proofs
        totals = [ordered]@{
            logical_system_dns_queries = 2
            http_requests = 0
            tls_connections = 0
            source_content_bytes = 0
        }
        rollback_performed = $false
        kill_switch = "TRIPPED_UNCHANGED"
        all_seven_m6_7_permissions = "NOT_AUTHORIZED"
        offline_projection_grant = "0/1_UNCONSUMED"
        seed_construction_grant = "0/1_UNCONSUMED"
    }
    Write-Evidence $evidence $repositoryRoot
}
catch {
    $failure = $_.Exception.Message
    $rollback = $null
    if ($mutationStarted) {
        try {
            netsh interface ipv4 set dnsservers name=13 source=dhcp | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "ROLLBACK_NETSH_FAILED" }
            Clear-DnsClientCache
            $rollback = Get-LocalSnapshot
        }
        catch {
            $rollback = [ordered]@{ failure = $_.Exception.Message }
        }
    }
    $evidence = [ordered]@{
        record_type = "M67_ELEVATED_LOCAL_DNS_REMEDIATION_EVIDENCE"
        version = "1.0.0"
        state = "LOCAL_DNS_RESOLVER_REMEDIATION_ROLLED_BACK_BLOCKED"
        terminal = $true
        grant_consumed = $true
        consumed_at = $consumedAt
        observed_at = [DateTimeOffset]::UtcNow.ToString("o")
        failure = $failure
        authorization_record_sha256 = (Get-FileHash -Algorithm SHA256 $authorizationPath).Hash.ToLowerInvariant()
        executable_sha256 = $scriptSha256
        elevation = $elevation
        before = $before
        rollback = $rollback
        http_requests = 0
        tls_connections = 0
        source_content_bytes = 0
        kill_switch = "TRIPPED_UNCHANGED"
        all_seven_m6_7_permissions = "NOT_AUTHORIZED"
        offline_projection_grant = "0/1_UNCONSUMED"
        seed_construction_grant = "0/1_UNCONSUMED"
    }
    Write-Evidence $evidence $repositoryRoot | Out-Null
    throw
}
