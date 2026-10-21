# Infrastructure Architecture Principles

Evaluate every solution submission against the principles below. For each one,
decide whether the submission PASSes, raises a CONCERN, or FAILs, and cite the
evidence from the submission.

## 1. Infrastructure as code

All infrastructure is defined in version-controlled code (Terraform, Helm,
Pulumi, ...). No manual console changes; drift is detectable and corrected.

## 2. Environment parity

Dev, staging, and production differ only in configuration values and scale,
not in architecture. What is tested is what ships.

## 3. High availability

No single point of failure for critical paths. Services span at least two
availability zones, and the loss of one zone degrades but does not stop service.

## 4. Scalability

Capacity scales horizontally by adding instances, not by resizing machines.
Scaling triggers are based on measured load, and limits are explicit.

## 5. Security by default

Network traffic is denied unless explicitly allowed. Data is encrypted in
transit and at rest. Identities use least-privilege roles; no long-lived
static credentials.

## 6. Immutable infrastructure

Servers and containers are replaced, never patched in place. A running
instance can always be rebuilt from the same artifact and configuration.

## 7. Backup and disaster recovery

Every stateful component has automated backups, a tested restore procedure,
and a stated RPO/RTO that matches the business criticality of the data.

## 8. Network segmentation

Public, private, and data tiers are separated. Databases and internal
services are not reachable from the public internet.

## 9. Cost awareness

Resources are sized to actual need, non-production environments can be
scaled down, and the design states its expected cost drivers.

## 10. Operational automation

Deployment, rollback, scaling, and certificate/secret rotation are automated.
Routine operations do not require shell access to production machines.
