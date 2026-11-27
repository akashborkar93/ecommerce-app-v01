# AWS Deployment Guide (EC2 + Docker + RDS + ALB)

You perform every step in this guide. The application only needs the interface in the README's "Deployment contract" section.

```
Internet -> Route 53 -> ALB (HTTPS, ACM cert) -> EC2 (Docker, FastAPI :8000) -> RDS PostgreSQL
```

Region used in examples: `us-east-1` (matches your `~/.aws/config`). Names like `ecommerce-*` are suggestions.

For the execution history of the deployed `api.akashcloud.online` stack,
including actual tool usage, permission errors, troubleshooting, and known
gaps in the retained command history, see
[`AWS_DEPLOYMENT_EXECUTION_RECORD.md`](./AWS_DEPLOYMENT_EXECUTION_RECORD.md).
The execution record describes what happened; this guide remains the
recommended repeatable procedure.

Rough monthly cost if left running 24/7 (check current pricing): ALB about $16-20, RDS db.t4g.micro about $13 plus storage, EC2 t3.micro about $8. No NAT Gateway in this design, which avoids about $33/month. Set a budget alarm first and tear down when you are done (Step 13).

---

## Step 0. Prerequisites and account safety

1. **Do not paste credentials into chat, files, or the repo.** If any access key was ever shared, rotate it.
2. Do not use the root user for daily work. Use an IAM Identity Center user or an IAM user with MFA and admin-level permissions for this learning project.
3. **For a new deployment, keep AWS operations in AWS.** Create resources in the browser console; run host commands on EC2 through Session Manager (Step 6). The only planned local activity is uploading project files to GitHub in your browser (Step 3). You do not need the AWS CLI or Docker on your PC. The historical deployment did use the local AWS CLI for some early provisioning; see the execution record.
4. Billing console: create a **Budget** (for example $20/month with an email alert).
5. Pick one region and stay in it for every resource.
6. The Docker image is built **on the EC2 instance itself**, so it always matches the instance CPU. No ECR repository is needed. Use a `t3` (x86) instance; the `t3.micro` has 1 GiB RAM, so add the swap file in Step 6 before building.

## Step 1. Network (VPC)

Console: VPC > Create VPC > "VPC and more".
- Name `ecommerce`, CIDR `10.0.0.0/16`
- 2 Availability Zones
- 2 public subnets, 2 private subnets
- NAT gateways: **None**
- VPC endpoints: None (S3 gateway endpoint is fine)
- Enable DNS hostnames and DNS resolution

Layout:
| Subnets | Contains | Why |
|---|---|---|
| Public (2 AZs) | ALB, the EC2 instance | ALB needs 2 AZs; EC2 needs internet to reach GitHub, Docker Hub and package mirrors |
| Private (2 AZs) | RDS | Database never reachable from the internet |

A more locked-down option is EC2 in private subnets plus a NAT gateway or VPC endpoints for S3/Secrets Manager/SSM. That costs more; start simple.

## Step 2. Security groups

Create three in the `ecommerce` VPC. Reference groups by ID rather than IP ranges.

| Group | Inbound | Source |
|---|---|---|
| `ecommerce-alb-sg` | TCP 80, 443 | 0.0.0.0/0 |
| `ecommerce-app-sg` | TCP 8000 | `ecommerce-alb-sg` |
| `ecommerce-db-sg` | TCP 5432 | `ecommerce-app-sg` |

Leave outbound as the default (all). **Do not open port 22.** Use SSM Session Manager to get a shell (Step 5).

## Step 3. Put the code on GitHub (browser only)

The project exists only on your PC, so EC2 needs to fetch it from GitHub.

1. On github.com: New repository `ecommerce-api`. Prefer **private**.
2. Upload the contents of your project folder (`D:\My Study\Claude_dev\Nov\PROJ-ecommerce-App-26112026`) with "Add file > Upload files". Drag in `app`, `migrations`, `scripts`, `tests`, `docs`, `Dockerfile`, `requirements.txt`, `requirements-dev.txt`, `alembic.ini`, `.dockerignore`, `.gitignore`, `.env.example` and `README.md`.
3. **Do not upload** `.venv`, `.git`, `.pytest_cache`, `.claude` or any real `.env` file.
4. If the repo is private, create a **fine-grained personal access token** with read-only "Contents" access to this one repo. You will paste it on EC2 in Step 7 and must not save it in a file or in chat. Making the repo public avoids the token, but then everyone can read the code.
5. Tag a release (Releases > Create a new release > tag `v1.0.0`). Explicit tags let you roll back.

## Step 4. RDS PostgreSQL

1. RDS > Subnet groups > create `ecommerce-db-subnets` using the **two private subnets**.
2. RDS > Create database:
   - Engine PostgreSQL (16.x), template **Free tier / Dev-Test**
   - Single-AZ for learning (Multi-AZ doubles the cost)
   - Instance `db.t4g.micro`, storage 20 GiB gp3
   - DB instance identifier `ecommerce-db`, initial database name `ecommerce`
   - Credentials: master user `ecommerce_admin`, **Manage master credentials in AWS Secrets Manager**
   - VPC `ecommerce`, subnet group above, **Public access: No**, security group `ecommerce-db-sg`
   - Backups: keep 7-day retention
3. After it is available, note the **endpoint** hostname. This is your `DATABASE_HOST`.
4. Note the secret ARN (RDS > your DB > Configuration > Master credentials). It stores the username and password as JSON.

Hardening to do later: create a separate least-privilege application user instead of running the app as the master user.

## Step 5. IAM role for the EC2 instance

IAM > Roles > Create role > AWS service > EC2. Name `ecommerce-ec2-role`.

Attach:
- `AmazonSSMManagedInstanceCore` (shell via Session Manager, no SSH)
- An inline policy allowing only your secret:
  ```json
  {
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "<your RDS secret ARN>"
    }]
  }
  ```
Optional: `CloudWatchAgentServerPolicy` if you want container logs in CloudWatch.

## Step 6. EC2 instance

1. EC2 > Launch instance:
   - AMI **Amazon Linux 2023**, type `t3.micro` (x86)
   - No key pair needed (use SSM)
   - Network: VPC `ecommerce`, a **public subnet**, auto-assign public IP **enabled**
   - Security group `ecommerce-app-sg`
   - IAM instance profile `ecommerce-ec2-role`
   - Metadata: require IMDSv2
2. Connect: EC2 > Connect > **Session Manager**.
3. In the Session Manager terminal (this is the only place you run bash), install Docker, git and jq, and add swap so the image build does not run out of memory:
   ```bash
   sudo dnf install -y docker git jq
   sudo systemctl enable --now docker

   sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
   sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
   ```

## Step 7. Build, migrate and start the container

All of this runs in the Session Manager terminal on the instance. Replace the placeholders. The password is fetched from Secrets Manager at run time, never written into a file or the image.

First fetch the code and build the image. **This directory on EC2 is your project root.**

```bash
cd ~
# public repo:
git clone --branch v1.0.0 https://github.com/<your-user>/ecommerce-api.git
# private repo: use the token only for this command; it is not stored
#   read -s -p "GitHub token: " GH_TOKEN; echo
#   git clone --branch v1.0.0 https://x-access-token:$GH_TOKEN@github.com/<your-user>/ecommerce-api.git
#   unset GH_TOKEN
cd ecommerce-api            # the folder containing the Dockerfile
sudo docker build -t ecommerce-api:1.0.0 .
```

Note: with a token in the clone URL, `.git/config` keeps it. Run `git remote set-url origin https://github.com/<your-user>/ecommerce-api.git` afterwards, or delete the folder after building.

Then set the variables and run the app:

```bash
REGION=us-east-1
IMAGE=ecommerce-api:1.0.0
SECRET_ARN="<rds secret arn>"
DB_HOST="<rds endpoint hostname>"

SECRET=$(aws secretsmanager get-secret-value --region $REGION --secret-id "$SECRET_ARN" --query SecretString --output text)
DB_USER=$(echo "$SECRET" | jq -r .username)
DB_PASS=$(echo "$SECRET" | jq -r .password)

# 1) one-off migration
sudo docker run --rm \
  -e DATABASE_HOST=$DB_HOST -e DATABASE_NAME=ecommerce \
  -e DATABASE_USER=$DB_USER -e DATABASE_PASSWORD="$DB_PASS" \
  $IMAGE alembic upgrade head

# 2) optional demo data
sudo docker run --rm \
  -e DATABASE_HOST=$DB_HOST -e DATABASE_NAME=ecommerce \
  -e DATABASE_USER=$DB_USER -e DATABASE_PASSWORD="$DB_PASS" \
  $IMAGE python -m scripts.seed

# 3) the API
sudo docker run -d --name ecommerce-api --restart unless-stopped -p 8000:8000 \
  -e DATABASE_HOST=$DB_HOST -e DATABASE_NAME=ecommerce \
  -e DATABASE_USER=$DB_USER -e DATABASE_PASSWORD="$DB_PASS" \
  -e APP_ENV=production -e LOG_LEVEL=INFO \
  $IMAGE

curl -s localhost:8000/health
curl -s localhost:8000/ready
curl -s localhost:8000/products
```

Expect `{"status":"healthy"}`, `{"status":"ready"}` and the four seeded products. `DATABASE_NAME` is the database name you set at creation (`ecommerce`), not the RDS instance identifier.

Note: `-e DATABASE_PASSWORD=...` is visible via `docker inspect` on that host. That is acceptable for this phase; ECS Fargate with native secret injection is the cleaner later step.

If `/ready` fails, see Troubleshooting.

## Step 8. Load balancer and target group

1. EC2 > Target Groups > Create:
   - Type **Instances**, protocol HTTP, port **8000**, VPC `ecommerce`
   - Health check path `/health` (use `/ready` if you want DB outages to mark the target unhealthy), interval 15s, healthy threshold 2, timeout 5s (above `DATABASE_CONNECT_TIMEOUT` if you use `/ready`)
   - Register your instance on port 8000
2. EC2 > Load Balancers > Create **Application Load Balancer**:
   - Internet-facing, IPv4, VPC `ecommerce`, the **two public subnets**
   - Security group `ecommerce-alb-sg`
   - Listener HTTP :80 forwarding to the target group
3. Wait for the target to show **healthy**, then test the ALB DNS name:
   ```bash
   curl http://<alb-dns-name>/health
   curl http://<alb-dns-name>/products
   ```

## Step 9. Domain, certificate and HTTPS

You need a domain you control (register one in Route 53 or point an existing one at a Route 53 hosted zone).

1. **ACM** (same region as the ALB): Request a public certificate for `api.yourdomain.com`, DNS validation. Click "Create records in Route 53". Wait for status **Issued**.
2. ALB > Listeners > Add **HTTPS :443**: forward to the target group, select the ACM certificate, policy `ELBSecurityPolicy-TLS13-1-2-2021-06` (or the current recommended one).
3. Edit the HTTP :80 listener: **redirect to HTTPS 443** (301).
4. **Route 53** > your hosted zone > Create record: `api` type **A**, **Alias** to the ALB.
5. Test: `curl https://api.yourdomain.com/health` and open `https://api.yourdomain.com/docs`.

TLS ends at the ALB. The app and ALB talk plain HTTP inside the VPC, which is fine for this design.

## Step 10. Verification checklist

- [ ] `https://api.yourdomain.com/health` returns 200
- [ ] `https://api.yourdomain.com/ready` returns 200
- [ ] `POST /products` and `POST /customers`, then `POST /orders`, succeed
- [ ] Ordering more than stock returns 409
- [ ] HTTP redirects to HTTPS
- [ ] You cannot connect to RDS from your laptop (it is private)
- [ ] You cannot reach port 8000 on the EC2 public IP directly (only the ALB can)
- [ ] `sudo docker logs ecommerce-api` shows JSON logs with request IDs and no password

## Step 11. Releasing a new version

```bash
# 1. In the browser: upload the changed files to GitHub and create release v1.0.1 (Step 3).
# 2. On EC2 (Session Manager):
cd ~ && rm -rf ecommerce-api
git clone --branch v1.0.1 https://github.com/<your-user>/ecommerce-api.git
cd ecommerce-api && sudo docker build -t ecommerce-api:1.0.1 .
# 3. Set IMAGE=ecommerce-api:1.0.1, run migrations (Step 7, command 1), then:
sudo docker rm -f ecommerce-api
# 4. Start again with the new IMAGE (Step 7, command 3)
```

Rollback: start the previous tag (the old image stays on the instance unless you prune it). Prefer backwards-compatible migrations so a rollback does not need a schema downgrade. This single-instance setup has a brief outage during the swap; zero-downtime needs 2 instances or ECS.

## Step 12. Observability (optional, small)

- Logs: run the container with `--log-driver=awslogs --log-opt awslogs-region=us-east-1 --log-opt awslogs-group=/ecommerce/api --log-opt awslogs-create-group=true` and add the CloudWatch Logs permissions to the instance role.
- Alarms: ALB `UnHealthyHostCount` and `HTTPCode_Target_5XX_Count`, RDS `CPUUtilization` and `FreeStorageSpace`.

## Step 13. Teardown (to stop charges)

Delete in this order: Route 53 record, ALB, target group, EC2 instance, RDS instance (decide on a final snapshot), the GitHub token, Secrets Manager secret if you created one separately, security groups, VPC (deletes subnets and gateways), then the ACM certificate. Finally check Billing and Cost Explorer the next day.

---

## Troubleshooting

| Symptom | Likely cause | Check |
|---|---|---|
| Target `unhealthy` | App not running, SG blocks ALB, wrong port or path | `docker ps`; `app-sg` allows 8000 from `alb-sg`; health check path is `/health` |
| `/ready` returns 503 | App cannot reach DB | `db-sg` allows 5432 from `app-sg`; `DATABASE_HOST` is the endpoint; same VPC; credentials; `docker logs` |
| `/ready` slow then 503 | Connect timeout, usually a security group or routing | Same as above; the app fails fast after `DATABASE_CONNECT_TIMEOUT` |
| `docker pull` access denied | Missing ECR permission or expired login | Role has ECR read policy; redo `ecr get-login-password` |
| `exec format error` | Image arch differs from instance | Build for `linux/amd64` (t3) or `linux/arm64` (t4g) |
| App exits at start with validation error | A required env var is missing | `docker logs`; see README Configuration |
| `password authentication failed` | Wrong user/password or stale secret | Re-read the secret; check `DATABASE_NAME` |
| ACM stays "Pending validation" | CNAME record missing or wrong zone | Create the validation record in the correct hosted zone |
| ALB DNS works, domain does not | Alias record missing or DNS still propagating | Route 53 A alias to the ALB; wait for TTL |
| 502/504 from ALB | Target down or slow | Target health; app logs; SG; timeouts |

## Later improvements (separate phases)

Least-privilege DB user, Multi-AZ RDS, two instances behind the ALB, Auto Scaling, ECS Fargate, Infrastructure as Code (Terraform), CI/CD, WAF, CloudWatch dashboards.
