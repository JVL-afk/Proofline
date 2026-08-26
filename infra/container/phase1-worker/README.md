# Phase 1 worker image automation

The owner has authorized a system-managed build from the exact approved repository commit. The
owner does not supply an image URI or digest.

After AWS SSO and the appropriate reviewed Terraform authority exist, the automated build must:

1. verify a clean Git tree and record the exact commit;
2. resolve the approved Python 3.13 base image to an immutable registry digest;
3. build only the M1 HTTP worker and its locked runtime dependencies;
4. generate a dependency inventory and SBOM;
5. run vulnerability scanning and fail closed on an unresolved policy-blocking finding;
6. create or use deterministic ECR repository `m67-phase1-worker` in `us-east-2`;
7. push without granting any discovery or research permission;
8. retrieve the image digest from ECR control-plane evidence;
9. bind commit, build inputs, SBOM hash, scan hash, repository, image digest, builder identity, and
   timestamps in an immutable image evidence record;
10. inject the immutable `repository@sha256:<digest>` into the generated Phase 1 Terraform input.

The deployment identity is always the digest returned by the target registry after publication:

`DEPLOYMENT_IMAGE_DIGEST = REGISTRY_MANIFEST_OR_INDEX_DIGEST_PROVEN_AFTER_PUBLICATION`

A local image-store digest, config digest, archive digest, or pre-publication manifest digest is
supporting build evidence only. It must never be substituted for the registry-consumable digest in
Terraform. Publication authorization and runtime-deployment authorization are separate gates when
the registry digest is not already known. The immutable evidence retains the registry media type,
single-platform manifest or index relationship, config digest, ordered layer descriptors, platform,
source commit, SBOM, and scan result. Any representation transformation must be reproduced from the
frozen local image and compared byte-for-byte with the registry manifest before equivalence may be
accepted.

The production Dockerfile pins the Linux/amd64 Python 3.13 Alpine 3.22 platform manifest at
`sha256:7f7ee17311e0273954ffe76a7b84a2d8c8ecf16f9992e780e4d46c86175df431`.
Its dependency stage exports only the `opintel-research-worker` runtime graph from `uv.lock` and
installs it with package hashes enforced. The runtime stage copies the M0/research source trees and
the deterministic opportunity/audit/demo/outreach/shadow core sources required by the existing
Phase 1 minimizer; it copies no local adapters or application routes. It runs as uid/gid 65532 and
removes runtime package-installation
tooling and its vendored dependencies after verifying the locked environment. The OpenSSL runtime
libraries are pinned to Alpine revision `3.5.7-r0`, and `xz-libs` is pinned to `5.8.3-r0`; these
revisions contain the fixes required by the frozen image scan. The root `.dockerignore` is an
allowlist:
local data, Git metadata, environment files, tests, documentation, and other workspace material do
not enter the build context.

No AI, browser, sender, delivery, person/contact, or business data enters the image. The worker task
remains at desired count zero until separately authorized. Image build/push is unavailable until an
authenticated AWS account and ECR authority exist.
