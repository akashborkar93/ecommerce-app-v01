# AWS Deployment Execution Record

This document records the deployment of the e-commerce API at
`https://api.akashcloud.online`, including which execution environments were
used, what was verified, and the issues encountered. It complements
[`AWS_DEPLOYMENT_GUIDE.md`](./AWS_DEPLOYMENT_GUIDE.md), which describes a
repeatable, console-first implementation.

## Important provenance note

The deployment history was not entirely console-only. Some early AWS resource
provisioning used the AWS CLI on the local workstation, even though the user
later explicitly requested that AWS work run on AWS, not locally. That
requirement was not fully honored at the time. This record calls out the
deviation rather than presenting the deployment as a click-by-click console
build.

The available session record does not preserve the exact local CLI command
history or reliably map every early resource to its creation tool. Do not infer
that a resource was created in the console just because it is listed below.
For an auditable per-resource timeline, inspect AWS CloudTrail Event history
for the deployment period in `us-east-1`. No credentials, account number,
secret values, or full resource ARNs are recorded here.

## Deployment summary

| Item | Deployed configuration |
|---|---|
| Region | `us-east-1` (US East, N. Virginia) |
| Domain | `api.akashcloud.online` |
| DNS | Route 53 hosted zone for `akashcloud.online`; Namecheap delegates the domain to Route 53; an alias record routes the API hostname to the ALB |
| Network | One VPC, two public subnets and two private subnets |
| Entry point | Internet-facing Application Load Balancer `ecommerce-alb` |
| Application | Amazon Linux 2023 EC2 `t3.micro`; Docker image `ecommerce-api:1.0.0`; API listens on port 8000 |
| Database | Private PostgreSQL 16 RDS instance `ecommerce-db`, database `ecommerce`, 20 GiB gp3, seven-day backup retention |
| TLS | ACM public certificate for `api.akashcloud.online`; HTTPS listener on 443 forwards to the API target group |
| HTTP behavior | Port 80 returns an HTTP 301 redirect to HTTPS |
| Health check | Target group `ecommerce-api-tg` checks `/health` |

Traffic flow:

```text
Browser --HTTPS--> Route 53 name --> ALB :443 --HTTP--> EC2 API :8000 --> private RDS :5432
Browser --HTTP----> ALB :80 --301 redirect--> HTTPS :443
```

TLS terminates at the ALB. The ALB-to-EC2 connection is HTTP inside the VPC;
this is not end-to-end TLS.

## What ran where

| Environment | Actions recorded |
|---|---|
| Local workstation | The Git tag/release `v1.0.0` was pushed from the local repository. Some early AWS provisioning also used the local AWS CLI. The exact commands and resource-by-resource mapping are not available in the retained history. |
| AWS Management Console | ACM certificate workflow and Route 53 validation integration; an attempted HTTPS listener workflow (it failed due to IAM authorization); HTTP listener redirect configuration; resource and deployment checks. The final HTTP-to-HTTPS redirect was configured in the ALB console. |
| AWS CloudShell | Created the HTTPS listener with one `aws elbv2 create-listener` call that included the certificate in the listener's default forward action. This worked around the console permission failure. CloudShell runs in AWS; it is distinct from a local terminal and from the EC2 shell. |
| EC2 via Systems Manager (SSM) | Application deployment work was performed on the EC2 host through SSM, including running the containerized API and database setup tasks. This is a shell on the instance, not AWS CloudShell. |
| Namecheap account | The domain's nameserver delegation was updated to the four Route 53 nameservers. DNS propagation was later confirmed. |

The exact command text for the CloudShell listener creation and the individual
SSM commands was not retained in the available record. The deployment guide
contains reusable examples, but those examples should not be mistaken for a
verbatim command log.

## Execution timeline

### 1. Discovery and source release

- Confirmed the AWS region and checked for pre-existing named deployment
  resources.
- The hosted zone did not exist at discovery time.
- Published the application source release/tag `v1.0.0` from the local Git
  repository.
- Some early resource creation then used the local AWS CLI. This was a process
  deviation from the user's later "no work in local" requirement; exact
  resource attribution is unavailable.

### 2. DNS and AWS foundation

- Created a Route 53 hosted zone and delegated the domain from Namecheap to the
  Route 53 nameservers.
- Provisioned the VPC, public/private subnets, security groups, IAM role/profile,
  private RDS database, EC2 instance, target group, and ALB.
- The historical notes do not establish which individual resources in this
  group were created with the local CLI versus console/CloudShell.
- DNS delegation took longer than expected. Once Namecheap delegation had
  propagated, the Route 53 nameservers were visible publicly and
  `api.akashcloud.online` resolved.

### 3. Application deployment and HTTP validation

- Used SSM to access the EC2 host and deploy the Dockerized API.
- Applied database migrations, seeded four products, and started the API.
- Confirmed the target became healthy and tested `/health`, `/ready`,
  `/products`, product/customer/order creation, and the insufficient-stock
  response through the ALB.
- During order testing, a request failed because the example JSON still
  contained literal `CUSTOMER_ID`/`PRODUCT_ID` placeholders. Replacing those
  placeholders with IDs returned by the API made the request valid.
- HTTP Swagger UI was used to guide endpoint testing while DNS/TLS work was
  pending.

### 4. TLS certificate and HTTPS

- An initial ACM certificate request was cancelled while the user chose to
  test over HTTP. Its validation record was removed.
- After DNS started resolving, requested a new ACM public certificate for
  `api.akashcloud.online` in `us-east-1`, using DNS validation and Route 53
  record creation.
- ACM reported DNS validation successful and the certificate status became
  **Issued**.
- The console's HTTPS listener flow failed and rolled back because the IAM
  identity was not authorized for
  `elasticloadbalancing:AddListenerCertificates`.
- In AWS CloudShell, created the HTTPS listener directly with the certificate
  included in the create-listener request. This succeeded.
- In the ALB console, edited the HTTP listener to return a 301 redirect to
  HTTPS.
- Verified HTTPS `/health`, Swagger UI at `/docs`, and the HTTP-to-HTTPS
  redirect. ACM later showed the certificate as **In use** and eligible for
  renewal.

## Errors and troubleshooting record

| Symptom/error | Diagnosis | Resolution or current status |
|---|---|---|
| Domain did not resolve promptly | Namecheap nameserver delegation and DNS propagation were still in progress; the Route 53 zone alone was not sufficient until the registrar delegation took effect. | Updated Namecheap nameservers to the Route 53 set, then waited and verified public DNS resolution before proceeding with certificate validation. |
| ACM certificate remained pending during the first HTTP-only attempt | DNS validation was not yet ready and the user chose not to wait for TLS at that point. | Cancelled the first request and removed its validation record. Later, after DNS worked, requested a new certificate; it validated and was issued. |
| ALB console failed to add HTTPS listener; operation rolled back | IAM authorization denied `elasticloadbalancing:AddListenerCertificates`. | Created the listener from AWS CloudShell with the certificate supplied in the initial listener action. This is a permission workaround, not a least-privilege fix. |
| IAM inline policy creation was denied | The IAM identity did not have permission to create the requested inline role policy. | Attached the managed `SecretsManagerReadWrite` policy to the EC2 role to unblock secret retrieval. This is broader than required; replace it with a scoped `secretsmanager:GetSecretValue` policy for the one database secret when an authorized administrator can do so. |
| Could not create/inspect a monthly budget alarm | Organization-level SCP restrictions denied budget access. | No budget alarm was created. Ask an AWS organization administrator to enable budget access and create an alert before extending the deployment. |
| Route 53 Domains `GetDomainDetail` was denied | An organization-level SCP blocked that Route 53 Domains API action. | Registrar nameserver setup was handled at Namecheap; this denial did not prevent Route 53 hosted-zone DNS from working. |
| Order POST failed in Swagger | The body contained placeholder strings instead of existing numeric customer/product IDs. | Create or list a customer and product first, then use their actual returned IDs in the order request. |
| API root `/` returns 404 | The app does not define a root route. | Use `/docs`, `/health`, `/ready`, or the documented API routes. This is expected behavior. |
| Local pytest suite not run | `pytest` was unavailable in the local environment and a dependency-install attempt was interrupted. | No successful full local test run is recorded. Do not report the test suite as passed; run it in a suitable environment before future code releases. |

## Verification results

Recorded successful checks:

- Target group reports the application healthy using `/health`.
- `https://api.akashcloud.online/health` returned `{"status":"healthy"}`.
- `https://api.akashcloud.online/docs` loaded Swagger UI.
- An HTTP request to the API hostname redirected to HTTPS.
- `/ready`, `/products`, product/customer/order creation, and an overstock order
  returning HTTP 409 were tested earlier over HTTP.

These are deployment smoke tests, not a complete security review or a passing
automated test suite.

## Important limitations and follow-up

- **No API authentication:** the API is publicly reachable. Do not use real or
  sensitive customer data, and do not promote the live API link as a production
  service until authentication, authorization, and abuse controls are addressed.
- **Database encryption:** the RDS instance was reported as not storage
  encrypted. Plan a migration/redeployment if encryption at rest is required;
  do not assume it can be enabled in place without impact.
- **Overbroad IAM policy:** `SecretsManagerReadWrite` is broader than necessary.
  Replace it with a secret-specific read policy when permissions allow.
- **No budget alarm:** organization policy prevented creation; arrange one with
  an administrator and monitor current AWS charges.
- **No local test pass:** run the focused and full test suites before shipping
  application changes.
- Keep the ACM certificate in `us-east-1` while it is attached to this ALB.
  DNS validation and the Route 53 validation record must remain available for
  managed renewal.
- Recheck actual AWS resource settings in the console before reproducing this
  stack. This record is a deployment log, not an IaC template or a guarantee
  that all resources still have the same state.

## Console inspection map for the next session

Use the AWS region selector to choose `us-east-1`, then inspect—do not recreate—
the live resources:

1. **Route 53 → Hosted zones:** confirm the zone and the API alias record.
2. **VPC → Your VPCs / Subnets / Security groups:** review the VPC layout and
   traffic boundaries.
3. **EC2 → Instances:** inspect the API instance and its security group/role.
4. **EC2 → Target Groups:** confirm the target is healthy and `/health` is the
   health-check path.
5. **EC2 → Load Balancers → Listeners:** confirm port 443 forwards to the target
   group and port 80 redirects to HTTPS.
6. **RDS → Databases:** confirm the database is private and review encryption,
   backup, and connectivity settings.
7. **Certificate Manager (ACM):** confirm the certificate is Issued and in use.
8. **IAM → Roles:** review the instance role and replace broad permissions only
   after confirming the app still retrieves its database secret.

For a repeatable step-by-step build, follow
[`AWS_DEPLOYMENT_GUIDE.md`](./AWS_DEPLOYMENT_GUIDE.md), check current AWS pricing
and permissions first, and prefer CloudShell/console/SSM over local AWS CLI when
the deployment requirement is that all AWS operations remain in AWS.
