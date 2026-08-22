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

The production Dockerfile pins the Linux/amd64 Python 3.13 slim-bookworm platform manifest at
`sha256:0f16c5d35fe6464ee471792ab3bb9116f911b65b3fbf10120c98d2bdc6332f48`.
Its dependency stage exports only the `opintel-research-worker` runtime graph from `uv.lock` and
installs it with package hashes enforced. The runtime stage copies only the M0/research source
trees required by that worker, removes unused build-oriented packages inherited from the base, and
runs as uid/gid 65532. The root `.dockerignore` is an allowlist:
local data, Git metadata, environment files, tests, documentation, and other workspace material do
not enter the build context.

No AI, browser, sender, delivery, person/contact, or business data enters the image. The worker task
remains at desired count zero until separately authorized. Image build/push is unavailable until an
authenticated AWS account and ECR authority exist.
