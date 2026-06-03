# Azure for AWS Solutions Architects Study Guide

A practical 15-section guide for architects who already know AWS and want to build strong Azure instincts without starting from zero.

This guide was assembled from official Microsoft Learn documentation and Azure Architecture Center comparisons reviewed on April 9, 2026. Use the linked docs as the current source of truth when a feature, limit, SLA, SKU, or pricing detail matters operationally.

---

## How to Use This Guide

- Study the sections in order if Azure is new to you.
- In each section, anchor on the AWS mental model first, then learn the Azure service names, then internalize the architectural differences.
- Treat the mappings as directional, not literal. Azure and AWS often solve the same problem with different control planes, resource hierarchies, and service boundaries.

### Translation Rules That Matter Early

- An Azure `subscription` is usually the closest match to an AWS account.
- An Azure `management group` is the closest match to an AWS Organization OU.
- An Azure `resource group` is a required lifecycle container. Deleting it deletes the resources inside it.
- Identity and authentication center on `Microsoft Entra ID`, while authorization to Azure resources typically uses `Azure RBAC`.
- Several AWS single-service mental models split into multiple Azure services.
- `Route 53` maps across `Azure DNS`, `Traffic Manager`, and sometimes `Front Door`.
- `IAM` maps across `Microsoft Entra ID`, `Azure RBAC`, `managed identities`, and `Azure Policy`.
- `CloudWatch` maps across `Azure Monitor`, `Application Insights`, `Log Analytics`, and `Activity Log`.

### AWS → Azure Service Translation Map

Internalize this before diving into sections. Treat mappings as directional — the consistency model, control plane, or billing dimension often differs.

| AWS | Azure | The difference that matters |
|---|---|---|
| Account / OU / Organization | Subscription / Management group / Tenant | Resource group is a *new* required layer; deleting it deletes its contents |
| IAM | Entra ID + Azure RBAC + Managed identities + Azure Policy | Identity (Entra) and resource authz (RBAC) are explicitly separate |
| VPC / Security Group + NACL | VNet / NSG | One NSG construct, no separate NACL layer |
| Route 53 | Azure DNS + Traffic Manager + Front Door | DNS, global routing, and edge delivery are three products |
| CloudFront / Global Accelerator | Front Door | One global edge/CDN/WAF product |
| ALB / NLB | Application Gateway (L7) / Load Balancer (L4) | Split by layer |
| EC2 / ASG | Virtual Machines / VM Scale Sets | Managed Disks are the default; no storage account to manage |
| S3 | Blob Storage | Redundancy (LRS/ZRS/GRS/GZRS) is an explicit, visible choice |
| EBS / EFS / FSx | Managed Disks / Azure Files / Azure NetApp Files | — |
| RDS / Aurora | Azure SQL Database / SQL Managed Instance / Flexible Server | No single Aurora-equivalent; choose by compatibility |
| DynamoDB | Cosmos DB | Multi-model, global, partition-key-sensitive; tunable consistency (5 levels) |
| ElastiCache | Azure Cache for Redis | — |
| Lambda | Azure Functions | — |
| Step Functions | Durable Functions (code) / Logic Apps (low-code) | Two distinct products |
| API Gateway | API Management | Broader: gateway + portal + lifecycle |
| ECS/EKS/Fargate | AKS / Container Apps / Container Instances | Container Apps is the serverless default; AKS for full K8s |
| ECR | Azure Container Registry | — |
| SQS / SNS | Queue Storage / Service Bus / Event Grid | Service Bus = enterprise queues+topics; Event Grid = events |
| Kinesis / MSK | Event Hubs (Kafka-compatible) | — |
| Redshift / Athena / EMR | Synapse / Databricks / Fabric | No single replacement |
| CloudWatch / X-Ray / CloudTrail | Azure Monitor / App Insights / Activity Log | KQL is the query language to learn |
| KMS / Secrets Manager / ACM | Key Vault (+ Managed HSM) | One vault covers keys, secrets, certs |
| GuardDuty / Security Hub | Microsoft Defender for Cloud | Unified posture + workload protection |
| WAF / Shield | Azure WAF (on App Gateway/Front Door) / DDoS Protection | WAF placement depends on your edge |
| CloudFormation / CDK | Bicep (+ ARM) / Terraform | Bicep is first-party; Terraform very common |
| Organizations SCP / Control Tower | Azure Policy / Landing Zones | Policy can *audit and remediate* existing resources |

### CLI & IaC Quickstart

Nearly every example below uses the Azure CLI (`az`) — the rough analog of the `aws` CLI — and **Bicep**, Azure's first-party IaC language (the CloudFormation/CDK analog).

```bash
az login
az account set --subscription "Production"          # pick the subscription (≈ AWS account)
az group create -n rg-app-prod -l eastus            # resource group = lifecycle container
az configure --defaults group=rg-app-prod location=eastus
az deployment group create -g rg-app-prod -f main.bicep   # deploy IaC (≈ aws cloudformation deploy)
```

```bicep
// main.bicep — declarative, ARM-native. `az bicep build` compiles to an ARM template.
param location string = resourceGroup().location
resource sa 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'stappprod${uniqueString(resourceGroup().id)}'
  location: location
  sku: { name: 'Standard_ZRS' }
  kind: 'StorageV2'
}
```

---

## Table of Contents

1. [Azure Foundations: Tenants, Subscriptions, Resource Groups, Regions](#1-azure-foundations-tenants-subscriptions-resource-groups-regions)
2. [Identity and Access Management](#2-identity-and-access-management)
3. [Networking, Connectivity, and Edge Delivery](#3-networking-connectivity-and-edge-delivery)
4. [Compute, Virtual Machines, and Scaling](#4-compute-virtual-machines-and-scaling)
5. [Object, Block, and File Storage](#5-object-block-and-file-storage)
6. [Relational Databases](#6-relational-databases)
7. [NoSQL, Cache, and Search](#7-nosql-cache-and-search)
8. [Containers and Kubernetes](#8-containers-and-kubernetes)
9. [Serverless, APIs, and Workflow Orchestration](#9-serverless-apis-and-workflow-orchestration)
10. [Messaging and Event Streaming](#10-messaging-and-event-streaming)
11. [Analytics, Data Lake, and AI](#11-analytics-data-lake-and-ai)
12. [Observability and Operations](#12-observability-and-operations)
13. [Security, Secrets, and Perimeter Protection](#13-security-secrets-and-perimeter-protection)
14. [Governance, Landing Zones, and Cost Management](#14-governance-landing-zones-and-cost-management)
15. [DevOps, IaC, Migration, Backup, and Disaster Recovery](#15-devops-iac-migration-backup-and-disaster-recovery)

---

## 1. Azure Foundations: Tenants, Subscriptions, Resource Groups, Regions

### AWS Mental Model

- `AWS Organizations`, `OUs`, `accounts`, `regions`, `availability zones`, `tags`, and the general account boundary you use for billing and governance.

### Azure Services and Concepts to Learn

- `Microsoft Entra tenant`
- `Management groups`
- `Subscriptions`
- `Resource groups`
- `Azure Resource Manager (ARM)`
- `Regions`, `Availability Zones`, and `paired regions`

### Key Differences to Internalize

- Azure has a stronger hierarchy mindset than AWS for many enterprise setups: `tenant -> management group -> subscription -> resource group -> resource`.
- A `resource group` is not just a label. It is a lifecycle container and deployment scope.
- Azure subnets are regional, not availability-zone-bound the way AWS subnets are.
- Azure HA decisions often layer `availability sets`, `availability zones`, and `paired regions`.
- ARM is the control plane across Azure. Many Azure concepts make more sense once you think in ARM scopes and resources.

### Hands-On

```bash
# The hierarchy, top-down: tenant → management group → subscription → resource group
az account management-group create --name mg-platform --display-name "Platform"
az account management-group create --name mg-workloads --display-name "Workloads"
az account management-group subscription add --name mg-workloads --subscription "Production"

# Resource group = lifecycle boundary. `az group delete` cascades to everything inside.
az group create -n rg-network-prod -l eastus --tags env=prod owner=platform
az group create -n rg-app-prod     -l eastus --tags env=prod owner=appteam
```

> Mental shift: in AWS you'd often use one account per environment; in Azure the common split is one **subscription** per environment, then many **resource groups** by workload inside it. The resource group has no AWS equivalent — it's a hard lifecycle container, not a tag.

### Start With These Docs

- [Azure for AWS professionals](https://learn.microsoft.com/en-us/azure/architecture/aws-professional/)
- [Compare AWS and Azure accounts](https://learn.microsoft.com/en-us/azure/architecture/aws-professional/accounts)
- [Regions and zones on Azure](https://learn.microsoft.com/en-us/azure/architecture/aws-professional/regions-zones)
- [Compare AWS and Azure resource management](https://learn.microsoft.com/en-us/azure/architecture/aws-professional/resources)
- [What is Azure Resource Manager?](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/overview)

### Practice

- Design a tenant structure for `dev`, `test`, `prod`, and `shared-services`.
- Decide where management groups stop and subscriptions begin.
- Write down when you would separate workloads by subscription instead of only by resource group.

---

## 2. Identity and Access Management

### AWS Mental Model

- `IAM users`, `IAM roles`, `IAM policies`, `IAM Identity Center`, `STS`, and `Organizations SCPs`.

### Azure Services and Concepts to Learn

- `Microsoft Entra ID`
- `Azure RBAC`
- `Managed identities`
- `Conditional Access`
- `Management groups`
- `Azure Policy`

### Key Differences to Internalize

- Azure splits identity and resource authorization more explicitly than AWS.
- `Microsoft Entra ID` handles identity, authentication, directory objects, app registrations, Conditional Access, and federation.
- `Azure RBAC` controls who can do what to Azure resources at a given scope.
- `Managed identities` are often the cleanest Azure equivalent to workload IAM roles.
- `Azure Policy` overlaps with some SCP-style governance goals, but it is not a direct SCP clone.

### AWS → Azure at a Glance

| AWS | Azure |
|---|---|
| IAM identity / users / SSO | Microsoft Entra ID |
| IAM policy on resources | Azure RBAC role assignment (at a scope) |
| EC2 instance profile / IRSA | Managed identity (system- or user-assigned) |
| STS AssumeRole | Entra workload identity federation |
| Organizations SCP | Azure Policy (deny/audit effects) |

### Hands-On

```bash
# Assign a built-in RBAC role at a scope (scope = MG / subscription / RG / resource)
az role assignment create \
  --assignee "alice@contoso.com" \
  --role "Storage Blob Data Reader" \
  --scope "/subscriptions/<sub-id>/resourceGroups/rg-app-prod"

# A managed identity is the clean equivalent of an EC2 instance role — no secrets to rotate
az identity create -n id-app -g rg-app-prod
# ...then grant THAT identity access to a resource, and attach it to the VM/App/Function.
```

```bicep
// Workload identity in IaC: a user-assigned identity + a role assignment on a Key Vault
resource id 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-app'
  location: location
}
resource kvRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(kv.id, id.id, 'kv-secrets-user')
  scope: kv
  properties: {
    principalId: id.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6') // Key Vault Secrets User
  }
}
```

### Start With These Docs

- [Compare AWS and Azure identity management solutions](https://learn.microsoft.com/en-us/azure/architecture/aws-professional/security-identity)
- [What is Microsoft Entra?](https://learn.microsoft.com/en-us/entra/fundamentals/what-is-entra)
- [Microsoft Entra ID documentation](https://learn.microsoft.com/en-us/entra/identity/)
- [Azure RBAC documentation](https://learn.microsoft.com/en-us/azure/role-based-access-control/)
- [Organize your resources with management groups](https://learn.microsoft.com/en-us/azure/governance/management-groups/overview)

### Practice

- Map an EC2 instance profile design to an Azure managed identity design.
- Recreate an AWS admin, read-only, and platform-ops model using Azure RBAC scopes.
- Identify where you would use Entra roles versus Azure RBAC roles.

---

## 3. Networking, Connectivity, and Edge Delivery

### AWS Mental Model

- `VPC`, `subnets`, `route tables`, `security groups`, `NACLs`, `NAT Gateway`, `ALB`, `NLB`, `Route 53`, `CloudFront`, `Global Accelerator`, `PrivateLink`, `Transit Gateway`, and `Direct Connect`.

### Azure Services and Concepts to Learn

- `Virtual Network (VNet)`
- `Subnets`
- `User-defined routes (UDRs)`
- `Network security groups (NSGs)`
- `Azure NAT Gateway`
- `Azure Load Balancer`
- `Application Gateway`
- `Azure DNS`
- `Traffic Manager`
- `Front Door`
- `Private Link` and `Private Endpoint`
- `VNet peering`
- `Virtual WAN`
- `ExpressRoute`

### Key Differences to Internalize

- Azure uses `NSGs` instead of the AWS combination of security groups plus NACLs.
- `Route 53` functionality is split. DNS hosting is usually `Azure DNS`; global DNS-level routing can be `Traffic Manager`; modern global app delivery is often `Front Door`.
- `Front Door` often ends up covering ground that AWS teams might split among `CloudFront`, `Global Accelerator`, and internet-facing load balancing patterns.
- `Application Gateway` is the closest mental match for `ALB`; `Azure Load Balancer` is closer to `NLB`.
- Azure hub-spoke and `Virtual WAN` are central reference patterns for multi-network architecture.

### AWS → Azure at a Glance

| AWS | Azure |
|---|---|
| VPC / subnet | VNet / subnet (regional, spans zones) |
| Security Group + NACL | NSG (one construct) |
| Route table | User-defined routes (UDRs) |
| Internet/NAT Gateway | Azure NAT Gateway |
| ALB / NLB | Application Gateway (L7) / Load Balancer (L4) |
| CloudFront + Global Accelerator + WAF | Front Door (Standard/Premium) |
| Route 53 (hosting / latency routing) | Azure DNS / Traffic Manager |
| PrivateLink | Private Link + Private Endpoint |
| Transit Gateway | Virtual WAN / VNet peering |
| Direct Connect | ExpressRoute |

### Hands-On

```bash
# A VNet with one subnet, an NSG, and a rule allowing HTTPS in
az network vnet create -g rg-network-prod -n vnet-prod \
  --address-prefix 10.0.0.0/16 --subnet-name snet-web --subnet-prefix 10.0.1.0/24
az network nsg create -g rg-network-prod -n nsg-web
az network nsg rule create -g rg-network-prod --nsg-name nsg-web -n allow-https \
  --priority 100 --destination-port-ranges 443 --access Allow --protocol Tcp --direction Inbound
az network vnet subnet update -g rg-network-prod --vnet-name vnet-prod -n snet-web --network-security-group nsg-web
```

> Unlike AWS, the subnet is *regional and spans all zones* — you do not create one subnet per AZ. Zonal HA is a property of the resources you place in the subnet, not the subnet itself.

### Start With These Docs

- [Compare AWS and Azure networking options](https://learn.microsoft.com/en-us/azure/architecture/aws-professional/networking)
- [What is Azure Front Door?](https://learn.microsoft.com/en-us/azure/frontdoor/front-door-overview)
- [What is Azure Application Gateway?](https://learn.microsoft.com/en-us/azure/application-gateway/overview)
- [Azure DNS documentation](https://learn.microsoft.com/en-us/azure/dns/)
- [Azure ExpressRoute documentation](https://learn.microsoft.com/en-us/azure/expressroute/)

### Practice

- Translate a three-tier VPC design into a hub-spoke Azure network.
- Decide when to use `Front Door`, `Application Gateway`, `Load Balancer`, or `Traffic Manager`.
- Rebuild an AWS `PrivateLink` pattern using `Private Endpoint`.

---

## 4. Compute, Virtual Machines, and Scaling

### AWS Mental Model

- `EC2`, `AMI`, `Auto Scaling Groups`, `Launch Templates`, `Spot`, `EBS`, and `instance store`.

### Azure Services and Concepts to Learn

- `Azure Virtual Machines`
- `VM sizes`
- `Virtual machine scale sets`
- `Azure Compute Gallery`
- `Spot VMs`
- `Availability sets`
- `Availability Zones`
- `Managed Disks`
- `Temporary storage`

### Key Differences to Internalize

- `VM scale sets` are the closest Azure equivalent to `Auto Scaling Groups`.
- Azure HA patterns for VMs are closely tied to `availability sets`, `zones`, and region design.
- Managed disks are the normal default. You do not manage the underlying storage accounts for VM disks.
- Azure compute choices are broader than just VMs. Many AWS teams overuse EC2 patterns when an Azure PaaS or container option would be better.

### AWS → Azure at a Glance

| AWS | Azure |
|---|---|
| EC2 instance | Virtual Machine |
| AMI | Azure Compute Gallery image |
| Auto Scaling Group | VM Scale Set (VMSS) |
| Launch Template | VMSS model / Bicep |
| Spot Instance | Spot VM (fixed discount, no bidding) |
| EBS | Managed Disk |
| Instance store | Temporary (ephemeral) disk |

### Hands-On

```bash
# A scale set (≈ ASG) with autoscale on CPU
az vmss create -g rg-app-prod -n vmss-web --image Ubuntu2204 \
  --vnet-name vnet-prod --subnet snet-web --instance-count 2 --zones 1 2 3
az monitor autoscale create -g rg-app-prod --resource vmss-web \
  --resource-type Microsoft.Compute/virtualMachineScaleSets --name web-autoscale --min-count 2 --max-count 10 --count 2
az monitor autoscale rule create -g rg-app-prod --autoscale-name web-autoscale \
  --condition "Percentage CPU > 70 avg 5m" --scale out 2
```

> Spreading the scale set across `--zones 1 2 3` is the Azure way to get AZ resilience — the equivalent of an ASG spanning subnets in multiple AZs.

### Start With These Docs

- [Compute services on Azure and AWS](https://learn.microsoft.com/en-us/azure/architecture/aws-professional/compute)
- [Azure Virtual Machines documentation](https://learn.microsoft.com/en-us/azure/virtual-machines/)
- [Introduction to Azure Managed Disks](https://learn.microsoft.com/en-us/azure/virtual-machines/managed-disks-overview)
- [Virtual machine scale sets documentation](https://learn.microsoft.com/en-us/azure/virtual-machine-scale-sets/)

### Practice

- Map an EC2 fleet that uses ASGs and EBS to Azure VMs, VMSS, and Managed Disks.
- Decide when to use Spot VMs in Azure and what workloads should avoid them.
- Compare an availability-set design with an availability-zone design for the same app.

---

## 5. Object, Block, and File Storage

### AWS Mental Model

- `S3`, `EBS`, `EFS`, `FSx`, and `Glacier`.

### Azure Services and Concepts to Learn

- `Azure Blob Storage`
- `Azure Data Lake Storage Gen2`
- `Managed Disks`
- `Azure Files`
- `Azure NetApp Files`
- `Archive`, `Cool`, and `Hot` tiers
- `LRS`, `ZRS`, `GRS`, and `GZRS`

### Key Differences to Internalize

- `Blob Storage` is the main S3-like object store.
- `Azure Data Lake Storage Gen2` is not a separate storage product in the same way teams often imagine it. It is built on top of Blob with hierarchical namespace features.
- Azure makes storage redundancy choices highly visible in architecture design.
- `Azure Files` is a managed file share service for SMB/NFS style workloads. `Azure NetApp Files` is the higher-performance shared file option for more demanding workloads.

### AWS → Azure at a Glance

| AWS | Azure | Notes |
|---|---|---|
| S3 | Blob Storage | Tiers: Hot / Cool / Cold / Archive |
| S3 Glacier | Blob Archive tier | Rehydration latency applies |
| EBS | Managed Disk | Standard HDD / SSD / Premium / Ultra |
| EFS | Azure Files | SMB/NFS shares |
| FSx for NetApp | Azure NetApp Files | High-performance shared files |
| S3 cross-region replication | GRS / GZRS redundancy | Redundancy is a SKU choice, not a separate feature |

### Hands-On

```bash
# A storage account (the container for blobs/files/queues/tables), a container, and an upload.
# SKU encodes redundancy: Standard_LRS (zone-local) | Standard_ZRS | Standard_GRS | Standard_GZRS
az storage account create -g rg-app-prod -n stappprod001 --sku Standard_GZRS --kind StorageV2
az storage container create --account-name stappprod001 -n uploads --auth-mode login
az storage blob upload --account-name stappprod001 -c uploads -n report.pdf -f ./report.pdf --auth-mode login

# Lifecycle: tier to Cool after 30d, Archive after 90d, delete after 365d (≈ S3 lifecycle)
az storage account management-policy create --account-name stappprod001 -g rg-app-prod --policy @lifecycle.json
```

> The redundancy decision (`LRS` → `GZRS`) is made *at the storage account* and is far more front-and-center than in S3, where durability is implicit. Choose it deliberately per dataset.

### Start With These Docs

- [Compare storage in Azure and AWS](https://learn.microsoft.com/en-us/azure/architecture/aws-professional/storage)
- [Introduction to Azure Blob Storage](https://learn.microsoft.com/en-us/azure/storage/blobs/storage-blobs-introduction)
- [Introduction to Azure Files](https://learn.microsoft.com/en-us/azure/storage/files/storage-files-introduction)
- [Introduction to Azure Managed Disks](https://learn.microsoft.com/en-us/azure/virtual-machines/managed-disks-overview)
- [Azure Storage documentation](https://learn.microsoft.com/en-us/azure/storage/)

### Practice

- Take three AWS datasets and choose Azure storage types and redundancy modes for each.
- Explain when `Blob`, `Azure Files`, and `Managed Disks` are the wrong choice for a workload.
- Design an archival strategy that mirrors `S3 Standard`, `S3 IA`, and `Glacier` style thinking.

---

## 6. Relational Databases

### AWS Mental Model

- `RDS`, `Aurora`, and self-managed databases on `EC2`.

### Azure Services and Concepts to Learn

- `Azure SQL Database`
- `Azure SQL Managed Instance`
- `SQL Server on Azure VMs`
- `Azure Database for PostgreSQL`
- `Azure Database for MySQL`

### Key Differences to Internalize

- Azure does not have one simple brand-equivalent to `Aurora`. Choose based on engine compatibility, PaaS depth, failover model, and operational needs.
- `Azure SQL Database` is strong for cloud-native SQL Server-compatible workloads.
- `Azure SQL Managed Instance` is the nearer fit when you need more SQL Server compatibility than Azure SQL Database offers.
- If you were self-managing on EC2, Azure often still gives you the option to run the engine on a VM, but you should justify why PaaS is not good enough.

### AWS → Azure at a Glance

| AWS | Azure | When |
|---|---|---|
| RDS for PostgreSQL/MySQL | Azure Database for PostgreSQL/MySQL — Flexible Server | Cloud-native OSS engines |
| RDS for SQL Server | Azure SQL Database | Cloud-native, SQL Server-compatible |
| RDS SQL Server (high compat) | Azure SQL Managed Instance | Near-100% SQL Server surface (CLR, Agent, cross-db) |
| Aurora | (no single equivalent) | Pick by engine + scale needs |
| SQL Server on EC2 | SQL Server on Azure VM | Only when PaaS can't meet a requirement |

### Hands-On

```bash
# Managed Postgres (Flexible Server) with zone-redundant HA — the RDS Multi-AZ analog
az postgres flexible-server create -g rg-app-prod -n pg-app-prod \
  --tier GeneralPurpose --sku-name Standard_D2ds_v5 \
  --high-availability ZoneRedundant --version 16 \
  --vnet vnet-prod --subnet snet-data

# Azure SQL Database (vCore, serverless tier auto-pauses like Aurora Serverless)
az sql server create -g rg-app-prod -n sql-app-prod --admin-user appadmin --admin-password '<secret>'
az sql db create -g rg-app-prod -s sql-app-prod -n appdb \
  --edition GeneralPurpose --compute-model Serverless --family Gen5 --capacity 2 --auto-pause-delay 60
```

> `--high-availability ZoneRedundant` is the Multi-AZ equivalent. For read scale-out, add read replicas; there's no Aurora-style shared storage layer, so replication is logical/physical per engine.

### Start With These Docs

- [Compare AWS and Azure database technology](https://learn.microsoft.com/en-us/azure/architecture/aws-professional/databases)
- [Azure SQL documentation](https://learn.microsoft.com/en-us/azure/azure-sql/)
- [What is Azure Database for PostgreSQL?](https://learn.microsoft.com/en-us/azure/postgresql/overview)
- [Azure Database for MySQL documentation](https://learn.microsoft.com/en-us/azure/mysql/)

### Practice

- Map one `Aurora PostgreSQL`, one `RDS SQL Server`, and one self-managed MySQL workload into Azure targets.
- Write down what would make you choose `SQL Managed Instance` over `Azure SQL Database`.
- Compare operational responsibilities across PaaS DB, managed instance, and DB-on-VM options.

---

## 7. NoSQL, Cache, and Search

### AWS Mental Model

- `DynamoDB`, `ElastiCache`, `OpenSearch`, `DocumentDB`, and `Keyspaces`.

### Azure Services and Concepts to Learn

- `Azure Cosmos DB`
- `Azure Cache for Redis`
- `Azure AI Search`
- `Azure Data Explorer` for some time-series and log analytics cases

### Key Differences to Internalize

- `Cosmos DB` is one of the biggest mental-model shifts for AWS architects. It is globally distributed, SLA-heavy, multi-model, and extremely sensitive to good partition-key design.
- `DynamoDB` and `Cosmos DB` feel similar in some application patterns, but their APIs, consistency options, throughput models, and multi-region behaviors differ enough that you should not assume direct portability.
- `Redis` is still Redis. The cloud architecture choices around placement, networking, persistence, and failover still matter.
- `OpenSearch` style needs may map to `Azure AI Search`, Elastic on Azure, or a different analytics stack depending on whether the problem is app search, log search, or full search cluster management.

### AWS → Azure at a Glance

| AWS | Azure |
|---|---|
| DynamoDB | Cosmos DB (NoSQL/Table/Mongo/Cassandra/Gremlin APIs) |
| DynamoDB DAX | Cosmos DB integrated cache |
| ElastiCache (Redis) | Azure Cache for Redis |
| DocumentDB | Cosmos DB for MongoDB |
| Keyspaces (Cassandra) | Cosmos DB for Apache Cassandra |
| OpenSearch (app search) | Azure AI Search |
| OpenSearch (log/time-series) | Azure Data Explorer |

### Hands-On

```bash
# Cosmos DB: account → database → container. Partition key choice is the #1 design decision.
az cosmosdb create -g rg-app-prod -n cosmos-app-prod --locations regionName=eastus failoverPriority=0 \
  --default-consistency-level Session     # 5 levels: Strong→BoundedStaleness→Session→ConsistentPrefix→Eventual
az cosmosdb sql database create -g rg-app-prod -a cosmos-app-prod -n appdb
az cosmosdb sql container create -g rg-app-prod -a cosmos-app-prod -d appdb -n orders \
  --partition-key-path "/tenantId" --throughput 400   # or --max-throughput for autoscale RU/s
```

> Two big shifts from DynamoDB: (1) Cosmos offers **five tunable consistency levels** (Session is the default sweet spot), not just eventual/strong; (2) throughput is provisioned in **Request Units (RU/s)**, shared or per-container — model your read/write mix in RUs the way you'd model DynamoDB RCU/WCU.

### Start With These Docs

- [Data and AI on Azure and AWS](https://learn.microsoft.com/en-us/azure/architecture/aws-professional/data-ai)
- [Azure Cosmos DB documentation](https://learn.microsoft.com/en-us/azure/cosmos-db/)
- [What is Azure Cache for Redis?](https://learn.microsoft.com/en-us/azure/azure-cache-for-redis/cache-overview)
- [Azure AI Search documentation](https://learn.microsoft.com/en-us/azure/search/)

### Practice

- Design a Cosmos DB data model for an app you would normally put on DynamoDB.
- Pick a partition key and explain the tradeoffs.
- Decide whether a given workload belongs on `Cosmos DB`, `Redis`, or a relational database.

---

## 8. Containers and Kubernetes

### AWS Mental Model

- `ECR`, `ECS`, `EKS`, `Fargate`, and `App Mesh`.

### Azure Services and Concepts to Learn

- `Azure Container Registry (ACR)`
- `Azure Kubernetes Service (AKS)`
- `Azure Container Apps`
- `Azure Container Instances`
- `Istio add-on for AKS`

### Key Differences to Internalize

- Teams coming from AWS often over-map everything to `AKS` because they know `EKS`. In Azure, `Container Apps` is frequently the better first stop for app teams who want serverless containers without owning Kubernetes.
- `AKS` is the answer when you truly want Kubernetes control and ecosystem flexibility.
- `ACR` is the normal `ECR` analog.
- `Container Apps` covers ground that AWS teams sometimes spread across `ECS`, `Fargate`, service discovery, and simple event-driven containers.

### AWS → Azure at a Glance

| AWS | Azure | Reach for it when |
|---|---|---|
| ECR | Azure Container Registry (ACR) | Always (image storage) |
| ECS on Fargate | Container Apps | Serverless containers, scale-to-zero, KEDA event scaling |
| EKS | AKS | You need full Kubernetes + ecosystem |
| Fargate one-off task | Container Instances (ACI) | Single short-lived container |
| App Mesh | Istio add-on for AKS / Container Apps built-in | Service mesh |

### Hands-On

```bash
# Build → push → run a serverless container, scale-to-zero, no cluster to manage (≈ ECS/Fargate)
az acr create -g rg-app-prod -n acrappprod --sku Standard
az acr build -r acrappprod -t api:v1 .                       # build in the cloud, push to ACR
az containerapp env create -g rg-app-prod -n cae-prod --location eastus
az containerapp create -g rg-app-prod -n api --environment cae-prod \
  --image acrappprod.azurecr.io/api:v1 --target-port 8080 --ingress external \
  --min-replicas 0 --max-replicas 10 --registry-server acrappprod.azurecr.io
```

> Default to **Container Apps** for app teams; only graduate to **AKS** when you genuinely need Kubernetes APIs, operators, or custom networking. The scale-to-zero + KEDA event scaling covers most ECS/Fargate use cases with far less to operate.

### Start With These Docs

- [Compute services on Azure and AWS](https://learn.microsoft.com/en-us/azure/architecture/aws-professional/compute)
- [What is Azure Kubernetes Service (AKS)?](https://learn.microsoft.com/en-us/azure/aks/what-is-aks)
- [Azure Container Apps overview](https://learn.microsoft.com/en-us/azure/container-apps/overview)
- [Azure Container Registry documentation](https://learn.microsoft.com/en-us/azure/container-registry/)

### Practice

- Take one `ECS on Fargate` workload and decide whether it belongs on `Container Apps` or `AKS`.
- Translate an `EKS + ECR + ALB ingress` pattern into Azure services.
- List the operational costs that change when you move from AKS to Container Apps.

---

## 9. Serverless, APIs, and Workflow Orchestration

### AWS Mental Model

- `Lambda`, `API Gateway`, and `Step Functions`.

### Azure Services and Concepts to Learn

- `Azure Functions`
- `Azure API Management`
- `Durable Functions`
- `Azure Logic Apps`

### Key Differences to Internalize

- `Azure Functions` is the primary Lambda equivalent.
- `Durable Functions` is the code-first orchestration model that most closely overlaps with `Step Functions` for developers who want orchestration in code.
- `Logic Apps` is the more integration-centric and low-code workflow product. It often becomes the better answer for enterprise integration than Durable Functions.
- `API Management` is broader than a simple API front door. It includes gateway, policies, developer portal, security, versioning, and lifecycle concerns.

### AWS → Azure at a Glance

| AWS | Azure |
|---|---|
| Lambda | Azure Functions |
| Lambda (provisioned concurrency) | Functions Premium plan (pre-warmed) |
| Step Functions (code-first) | Durable Functions |
| Step Functions (low-code/integration) | Logic Apps |
| API Gateway | API Management |

### Hands-On

```bash
# Create a Function App on the serverless Consumption plan, deploy code
az functionapp create -g rg-app-prod -n func-app-prod \
  --consumption-plan-location eastus --runtime node --runtime-version 20 \
  --functions-version 4 --storage-account stappprod001
func azure functionapp publish func-app-prod      # Azure Functions Core Tools
```

```js
// Durable Functions orchestrator — the Step Functions analog, but orchestration is *code*
const df = require("durable-functions");
module.exports = df.orchestrator(function* (ctx) {
  const order = yield ctx.df.callActivity("ReserveInventory", ctx.df.getInput());
  yield ctx.df.callActivity("ChargePayment", order);
  yield ctx.df.callActivity("SendConfirmation", order);   // fan-out/fan-in, retries, timers all in code
});
```

> Choose **Durable Functions** when engineers want orchestration expressed in code with source control and testing; choose **Logic Apps** when the workflow is integration-heavy (connectors to SaaS/enterprise systems) and better owned low-code.

### Start With These Docs

- [Azure Functions overview](https://learn.microsoft.com/en-us/azure/azure-functions/functions-overview)
- [Durable Functions overview](https://learn.microsoft.com/en-us/azure/azure-functions/durable-functions/durable-functions-overview)
- [Azure API Management - Overview and Key Concepts](https://learn.microsoft.com/en-us/azure/api-management/api-management-key-concepts)
- [What is Azure Logic Apps?](https://learn.microsoft.com/en-us/azure/logic-apps/logic-apps-overview)

### Practice

- Rebuild a `Lambda + API Gateway + Step Functions` design in Azure.
- Decide when orchestration should be in `Durable Functions` versus `Logic Apps`.
- Define where API auth, transformation, throttling, and developer onboarding belong in `API Management`.

---

## 10. Messaging and Event Streaming

### AWS Mental Model

- `SQS`, `SNS`, `EventBridge`, `Kinesis`, `Amazon MQ`, and sometimes `MSK`.

### Azure Services and Concepts to Learn

- `Queue Storage`
- `Service Bus`
- `Event Grid`
- `Event Hubs`

### Key Differences to Internalize

- `SQS` maps to two Azure answers depending on the problem. `Queue Storage` is the simpler queue. `Service Bus` is the richer enterprise messaging system.
- `SNS` style fan-out often maps to `Service Bus topics` or `Event Grid`, depending on semantics and subscribers.
- `EventBridge` thinking generally maps best to `Event Grid`.
- `Kinesis` or Kafka-style ingest patterns generally point toward `Event Hubs`.
- `Service Bus` is the place to look when you need durable queues, pub/sub, ordering patterns, sessions, or enterprise messaging semantics.

### AWS → Azure at a Glance

| AWS | Azure | Semantics |
|---|---|---|
| SQS (simple) | Queue Storage | Basic queue, huge scale, cheap |
| SQS (FIFO/DLQ/sessions) | Service Bus queue | Ordering, sessions, dead-lettering, transactions |
| SNS fan-out | Service Bus topics / Event Grid | Topics for messaging; Event Grid for events |
| EventBridge | Event Grid | Reactive event routing |
| Kinesis / MSK | Event Hubs | High-throughput streaming (Kafka-compatible endpoint) |

### Hands-On

```bash
# Service Bus topic + subscription = the SNS→SQS fan-out pattern, but one product
az servicebus namespace create -g rg-app-prod -n sb-app-prod --sku Standard
az servicebus topic create -g rg-app-prod --namespace-name sb-app-prod -n orders
az servicebus topic subscription create -g rg-app-prod --namespace-name sb-app-prod \
  --topic-name orders -n fulfillment --dead-lettering-on-message-expiration true

# Event Hubs for Kafka-style ingest (Kinesis analog) — partitions + consumer groups
az eventhubs namespace create -g rg-app-prod -n eh-app-prod --sku Standard --enable-kafka true
az eventhubs eventhub create -g rg-app-prod --namespace-name eh-app-prod -n telemetry --partition-count 8
```

> Decision rule: **Queue Storage** for dirt-simple queues; **Service Bus** the moment you need ordering, sessions, or DLQ; **Event Grid** for "react to a thing happened"; **Event Hubs** when you'd have reached for Kinesis or Kafka.

### Start With These Docs

- [Messaging services on Azure and AWS](https://learn.microsoft.com/en-us/azure/architecture/aws-professional/messaging)
- [Azure Service Bus Messaging documentation](https://learn.microsoft.com/en-us/azure/service-bus-messaging/)
- [What is Azure Event Grid?](https://learn.microsoft.com/en-us/azure/event-grid/overview)
- [What is Azure Event Hubs?](https://learn.microsoft.com/en-us/azure/event-hubs/event-hubs-about)
- [Queue Storage documentation](https://learn.microsoft.com/en-us/azure/storage/queues/)

### Practice

- Replace an `SNS -> SQS -> Lambda` fan-out design using Azure services.
- Decide when `Event Grid` is better than `Service Bus`.
- Decide when `Event Hubs` should sit in front of analytics or downstream processing.

---

## 11. Analytics, Data Lake, and AI

### AWS Mental Model

- `Athena`, `Glue`, `EMR`, `Redshift`, `Kinesis`, `Timestream`, `SageMaker`, `Rekognition`, and other AI services.

### Azure Services and Concepts to Learn

- `Azure Data Lake Storage Gen2`
- `Azure Data Factory`
- `Azure Synapse Analytics`
- `Azure Databricks`
- `Azure Data Explorer`
- `Azure AI services`
- `Microsoft Fabric` as an adjacent modern analytics platform you will see in current Azure docs

### Key Differences to Internalize

- Azure’s analytics landscape is wider than many AWS architects expect. There is no single answer that always replaces `Redshift + Glue + Athena + EMR`.
- `Data Factory` handles integration and orchestration.
- `Synapse` blends SQL, Spark, pipelines, and analytics workspace patterns.
- `Databricks` is a major first-class choice for lakehouse, Spark, streaming, data engineering, and AI workflows.
- `Data Explorer` is strong for log, time-series, and high-ingest interactive analytics use cases.
- AI services in Azure are split across specialized APIs and broader platform tooling, rather than one monolithic ML answer.

### AWS → Azure at a Glance

| AWS | Azure |
|---|---|
| Redshift | Synapse (dedicated SQL pool) / Microsoft Fabric Warehouse |
| Athena | Synapse serverless SQL / Fabric |
| Glue | Data Factory (orchestration/ETL) |
| EMR | Databricks / Synapse Spark |
| Kinesis Data Analytics | Stream Analytics / Data Explorer |
| SageMaker | Azure Machine Learning |
| Bedrock | Azure OpenAI / Azure AI Foundry |
| Rekognition / Comprehend / Textract | Azure AI services (Vision / Language / Document Intelligence) |

### Hands-On

```bash
# Serverless ad-hoc SQL over a data lake (≈ Athena): query Parquet in ADLS Gen2 directly
# (run inside Synapse serverless SQL pool)
```

```sql
-- Synapse serverless: external query over lake files, no cluster, pay per TB scanned (Athena-style)
SELECT region, SUM(amount) AS total
FROM OPENROWSET(
    BULK 'https://stappprod001.dfs.core.windows.net/lake/sales/*.parquet',
    FORMAT = 'PARQUET'
) AS rows
GROUP BY region;
```

> There is no single "Redshift replacement." For a modern build, evaluate **Microsoft Fabric** (the converged SaaS analytics platform) and **Databricks** first; reach for dedicated **Synapse** pools mainly for existing/portable warehouse workloads.

### Start With These Docs

- [Data and AI on Azure and AWS](https://learn.microsoft.com/en-us/azure/architecture/aws-professional/data-ai)
- [Introduction to Azure Data Factory](https://learn.microsoft.com/en-us/azure/data-factory/introduction)
- [What is Azure Synapse Analytics?](https://learn.microsoft.com/en-us/azure/synapse-analytics/overview-what-is)
- [What is Azure Databricks?](https://learn.microsoft.com/en-us/azure/databricks/introduction/)
- [What are Azure AI services?](https://learn.microsoft.com/en-us/azure/ai-studio/concepts/what-are-ai-services)

### Practice

- Map one `Athena + Glue` workload, one `Redshift` workload, and one `EMR/Spark` workload into Azure options.
- Explain when `Synapse` is enough and when `Databricks` is the better fit.
- Design a streaming path from ingestion to dashboard using `Event Hubs` plus an Azure analytics target.

---

## 12. Observability and Operations

### AWS Mental Model

- `CloudWatch`, `X-Ray`, `CloudTrail`, `Systems Manager`, and some operational reporting you might also get from `Config`.

### Azure Services and Concepts to Learn

- `Azure Monitor`
- `Application Insights`
- `Log Analytics`
- `Activity Log`
- `Azure Automation`

### Key Differences to Internalize

- Azure observability is deliberately split by concern. `Azure Monitor` is the umbrella, `Application Insights` handles APM, `Log Analytics` is the query/workspace layer, and `Activity Log` is the control-plane audit log.
- `Activity Log` is the closest control-plane analog to `CloudTrail`.
- Azure teams frequently use `KQL` for querying operational data, which becomes an important skill quickly.
- `Azure Automation` covers runbooks and automation patterns that many AWS teams might associate with `Systems Manager`.

### AWS → Azure at a Glance

| AWS | Azure |
|---|---|
| CloudWatch Metrics/Alarms | Azure Monitor Metrics + Alerts |
| CloudWatch Logs | Log Analytics workspace |
| X-Ray | Application Insights (distributed tracing) |
| CloudTrail | Activity Log |
| Systems Manager runbooks | Azure Automation |
| CloudWatch Logs Insights | KQL (Kusto Query Language) |

### Hands-On

```kql
// KQL in Log Analytics — the language you must learn. Errors per Container App, last hour.
ContainerAppConsoleLogs_CL
| where TimeGenerated > ago(1h) and Log_s contains "ERROR"
| summarize errors = count() by ContainerAppName_s, bin(TimeGenerated, 5m)
| order by TimeGenerated desc
```

```bash
# Wire an alert off a metric (≈ CloudWatch alarm) and an uptime/availability test
az monitor metrics alert create -g rg-app-prod -n high-cpu \
  --scopes "/subscriptions/<sub>/resourceGroups/rg-app-prod/providers/Microsoft.Compute/virtualMachineScaleSets/vmss-web" \
  --condition "avg Percentage CPU > 80" --window-size 5m --evaluation-frequency 1m
```

> The split is deliberate: **Azure Monitor** is the umbrella, **Application Insights** is APM/tracing, **Log Analytics** is the queryable store, **Activity Log** is the control-plane audit trail (your CloudTrail). Almost everything is queried with **KQL** — budget time to learn it early.

### Start With These Docs

- [Azure Monitor overview](https://learn.microsoft.com/en-us/azure/azure-monitor/fundamentals/overview)
- [Introduction to Application Insights - OpenTelemetry observability](https://learn.microsoft.com/en-us/azure/azure-monitor/app/app-insights-overview)
- [Activity log in Azure Monitor](https://learn.microsoft.com/en-us/azure/azure-monitor/essentials/activity-log)
- [What is Azure Automation?](https://learn.microsoft.com/en-us/azure/automation/overview)
- [Azure for AWS professionals](https://learn.microsoft.com/en-us/azure/architecture/aws-professional/)

### Practice

- Draw the Azure equivalent of your standard `CloudWatch + X-Ray + CloudTrail` setup.
- Write down which data belongs in metrics, logs, traces, and activity logs.
- Build a short KQL learning list before you go deep into Azure ops.

---

## 13. Security, Secrets, and Perimeter Protection

### AWS Mental Model

- `KMS`, `Secrets Manager`, `CloudHSM`, `GuardDuty`, `Security Hub`, `WAF`, and `Shield`.

### Azure Services and Concepts to Learn

- `Azure Key Vault`
- `Azure Key Vault Managed HSM`
- `Microsoft Defender for Cloud`
- `Azure Web Application Firewall`
- `Azure DDoS Protection`
- `Application Gateway WAF`
- `Front Door WAF`

### Key Differences to Internalize

- `Key Vault` combines several patterns AWS teams often split between `KMS`, `Secrets Manager`, and certificate management.
- `Defender for Cloud` combines posture and workload protection concepts that AWS teams often spread across `Security Hub`, `GuardDuty`, and additional tools.
- Network-layer DDoS defense and application-layer WAF are separate concerns in Azure, just as they should be architecturally.
- The place you insert WAF in Azure depends on whether your app edge is `Application Gateway` or `Front Door`.

### AWS → Azure at a Glance

| AWS | Azure |
|---|---|
| KMS | Key Vault (keys) |
| CloudHSM | Key Vault Managed HSM |
| Secrets Manager | Key Vault (secrets) |
| Certificate Manager (ACM) | Key Vault (certificates) |
| GuardDuty + Security Hub | Microsoft Defender for Cloud |
| AWS WAF | Azure WAF (on Front Door or App Gateway) |
| Shield (Standard/Advanced) | Azure DDoS Protection (Network/IP) |

### Hands-On

```bash
# Key Vault holds keys, secrets, AND certs in one place. Grant access via RBAC (not access policies).
az keyvault create -g rg-app-prod -n kv-app-prod --enable-rbac-authorization true
az keyvault secret set --vault-name kv-app-prod -n db-password --value '<secret>'

# App reads it at runtime via its managed identity — no secret in code or config:
#   https://kv-app-prod.vault.azure.net/secrets/db-password
```

```bicep
// WAF policy attached to Front Door, OWASP managed ruleset in Prevention mode
resource waf 'Microsoft.Network/FrontDoorWebApplicationFirewallPolicies@2022-05-01' = {
  name: 'wafprod'
  location: 'global'
  sku: { name: 'Premium_AzureFrontDoor' }
  properties: {
    policySettings: { enabledState: 'Enabled', mode: 'Prevention' }
    managedRules: { managedRuleSets: [ { ruleSetType: 'Microsoft_DefaultRuleSet', ruleSetVersion: '2.1' } ] }
  }
}
```

> Put WAF on **Front Door** when the edge is global/CDN-fronted; put it on **Application Gateway** when the entry point is a regional L7 LB inside a VNet. Use both only when you have both edges.

### Start With These Docs

- [Compare AWS and Azure identity management solutions](https://learn.microsoft.com/en-us/azure/architecture/aws-professional/security-identity)
- [About Azure Key Vault](https://learn.microsoft.com/en-us/azure/key-vault/general/overview)
- [Microsoft Defender for Cloud documentation](https://learn.microsoft.com/en-us/azure/defender-for-cloud/)
- [Azure DDoS Protection Overview](https://learn.microsoft.com/en-us/azure/ddos-protection/ddos-protection-overview)
- [What Is Azure Web Application Firewall on Azure Application Gateway?](https://learn.microsoft.com/en-us/azure/web-application-firewall/ag/ag-overview)

### Practice

- Replace an `AWS KMS + Secrets Manager` design with Azure services and access controls.
- Decide whether WAF belongs on `Application Gateway`, `Front Door`, or both.
- Explain how you would centralize cloud security posture across multiple subscriptions.

---

## 14. Governance, Landing Zones, and Cost Management

### AWS Mental Model

- `Organizations`, `Control Tower`, `Config`, `Trusted Advisor`, `Cost Explorer`, and `Budgets`.

### Azure Services and Concepts to Learn

- `Management groups`
- `Azure Policy`
- `Azure landing zones`
- `Azure Advisor`
- `Microsoft Cost Management`

### Key Differences to Internalize

- Azure landing zones are a core enterprise design pattern. Think of them as more than an account vending machine. They are a full platform architecture baseline for identity, networking, governance, management, and platform automation.
- `Azure Policy` can audit and remediate both existing and new resources, which often changes how teams think about governance.
- `Advisor` is the closest `Trusted Advisor` style service.
- Cost visibility and accountability can be driven at `management group`, `subscription`, and `resource group` scopes.

### AWS → Azure at a Glance

| AWS | Azure |
|---|---|
| Organizations SCP | Azure Policy (deny effect at a scope) |
| Control Tower | Azure Landing Zones (Cloud Adoption Framework) |
| Config (rules/remediation) | Azure Policy (audit + remediate) |
| Trusted Advisor | Azure Advisor |
| Cost Explorer / Budgets | Microsoft Cost Management + Budgets |

### Hands-On

```bash
# Guardrail as policy: deny any resource created outside approved regions (≈ an SCP)
az policy assignment create --name allowed-locations \
  --scope "/providers/Microsoft.Management/managementGroups/mg-workloads" \
  --policy "e56962a6-4747-49cd-b67b-bf8b01975c4c" \
  --params '{ "listOfAllowedLocations": { "value": ["eastus","eastus2"] } }'

# Budget that fires an action group (email/webhook) at 80% of target
az consumption budget create --budget-name prod-monthly --amount 5000 --time-grain Monthly \
  --category Cost --resource-group rg-app-prod
```

> Unlike SCPs (which only deny), **Azure Policy** can `audit`, `deny`, **and** `deployIfNotExists`/`modify` to *remediate* existing resources — e.g., auto-tagging or enabling diagnostics on anything non-compliant. That changes governance from gatekeeping to continuous enforcement.

### Start With These Docs

- [Organize your resources with management groups](https://learn.microsoft.com/en-us/azure/governance/management-groups/overview)
- [What is Azure Policy?](https://learn.microsoft.com/en-us/azure/governance/policy/overview)
- [What is an Azure landing zone?](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ready/landing-zone/)
- [Introduction to Azure Advisor](https://learn.microsoft.com/en-us/azure/advisor/advisor-overview)
- [What is Microsoft Cost Management](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/overview-cost-management)

### Practice

- Sketch a platform landing zone and at least two application landing zones.
- Define three guardrails you would implement with Azure Policy on day one.
- Decide what cost ownership belongs at management-group, subscription, and resource-group scope.

---

## 15. DevOps, IaC, Migration, Backup, and Disaster Recovery

### AWS Mental Model

- `CloudFormation`, `CDK`, `CodePipeline`, `CodeBuild`, `CodeDeploy`, `Migration Hub`, `DMS`, `AWS Backup`, and `Elastic Disaster Recovery`.

### Azure Services and Concepts to Learn

- `Azure Resource Manager`
- `Bicep`
- `Azure DevOps`
- `GitHub Actions for Azure`
- `Azure Migrate`
- `Azure Database Migration Service`
- `Azure Backup`
- `Azure Site Recovery`

### Key Differences to Internalize

- `Bicep` is the preferred first-party IaC language on top of ARM. ARM templates still matter, but Bicep is the better day-to-day authoring experience.
- Azure shops commonly standardize on either `Azure DevOps` or `GitHub Actions`, with GitHub plus Bicep/Terraform being especially common for newer platform work.
- `Azure Migrate` is the main discovery, assessment, and migration hub for many Azure adoption journeys.
- `Azure Backup` and `Azure Site Recovery` solve different problems. Backup protects recoverable data states; Site Recovery handles replication, failover, and workload continuity.

### AWS → Azure at a Glance

| AWS | Azure |
|---|---|
| CloudFormation | ARM templates / Bicep |
| CDK | Bicep (first-party) / Terraform |
| CodePipeline + CodeBuild | Azure Pipelines / GitHub Actions |
| CodeDeploy | Azure Pipelines deploy / Cloud-native rollouts |
| Migration Hub | Azure Migrate |
| DMS | Azure Database Migration Service |
| AWS Backup | Azure Backup |
| Elastic Disaster Recovery | Azure Site Recovery |

### Hands-On

```yaml
# GitHub Actions deploying Bicep with OIDC (no stored cloud secret — federated identity)
name: deploy
on: { push: { branches: [main] } }
permissions: { id-token: write, contents: read }
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
      - run: az deployment group create -g rg-app-prod -f main.bicep
```

> Prefer **OIDC workload-identity federation** (above) over a stored service-principal secret — it's the Azure equivalent of GitHub Actions assuming an AWS IAM role via OIDC, and it removes long-lived credentials from CI. Keep **Backup** (recover data states) and **Site Recovery** (replicate + fail over workloads) as separate line items in your DR plan; they answer different RPO/RTO questions.

### Start With These Docs

- [What is Bicep?](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/overview)
- [GitHub Actions for Azure](https://learn.microsoft.com/en-us/azure/developer/github/github-actions)
- [What is Azure Migrate?](https://learn.microsoft.com/en-us/azure/migrate/migrate-services-overview)
- [What is the Azure Backup service?](https://learn.microsoft.com/en-us/azure/backup/backup-overview)
- [About Site Recovery](https://learn.microsoft.com/en-us/azure/site-recovery/site-recovery-overview)

### Practice

- Translate one `CloudFormation` stack into a `Bicep` deployment plan.
- Design a migration runbook for VMs, databases, and web apps using `Azure Migrate`.
- Separate your backup strategy from your disaster recovery strategy in writing and make sure each service choice matches the right objective.

---

## Common Pitfalls for AWS Architects Moving to Azure

- **Forgetting the resource group is destructive.** It's not a tag — `az group delete` cascades to every resource inside. Group by lifecycle, not just by label.
- **Mapping everything to AKS because you know EKS.** Container Apps is the right first stop for most app teams; AKS is for when you truly need Kubernetes.
- **Treating Entra ID and Azure RBAC as one thing.** Entra is *identity*; RBAC is *resource authorization at a scope*. App registrations and directory roles live in Entra; "can this principal write to this storage account" is RBAC.
- **Ignoring the redundancy SKU.** `LRS` is zone-local. If you assumed S3-like durability, you may be one datacenter incident from data loss — choose `ZRS`/`GZRS` deliberately.
- **Putting WAF in the wrong place.** It belongs on whatever your actual edge is (Front Door *or* Application Gateway), not reflexively on both.
- **Underestimating Cosmos DB partition-key design.** A hot partition key caps throughput and inflates RU/s cost. This is the Cosmos equivalent of a bad DynamoDB partition key — design it up front.
- **Storing CI secrets instead of using OIDC.** Use workload-identity federation for GitHub Actions/Azure Pipelines; don't paste a service-principal secret.
- **Confusing Backup with Site Recovery.** Backup = recover data to a point in time. Site Recovery = replicate and fail a workload over to another region. You usually need both.
- **Assuming one subnet per AZ.** Azure subnets are regional and span zones; zonal HA is a property of the resources, not the subnet.

---

## Quick Reference: AWS → Azure

| Need | AWS | Azure |
|------|-----|-------|
| Account boundary | Account | Subscription (+ resource groups inside) |
| Org hierarchy | Organizations / OUs | Tenant / Management groups |
| Identity + authz | IAM | Entra ID + Azure RBAC |
| Workload identity | Instance profile / IRSA | Managed identity |
| Virtual network | VPC | VNet |
| Firewalling | Security Group + NACL | NSG |
| Global edge / CDN / WAF | CloudFront + GA + WAF | Front Door |
| L7 / L4 load balancer | ALB / NLB | App Gateway / Load Balancer |
| Object storage | S3 | Blob Storage |
| Managed relational | RDS / Aurora | Azure SQL / Flexible Server / SQL MI |
| Managed NoSQL | DynamoDB | Cosmos DB |
| Cache | ElastiCache | Azure Cache for Redis |
| Functions | Lambda | Azure Functions |
| Orchestration | Step Functions | Durable Functions / Logic Apps |
| Serverless containers | ECS/Fargate | Container Apps |
| Managed Kubernetes | EKS | AKS |
| Queue / pub-sub | SQS / SNS | Queue Storage / Service Bus / Event Grid |
| Streaming | Kinesis / MSK | Event Hubs |
| Data warehouse | Redshift | Synapse / Fabric / Databricks |
| ML platform | SageMaker | Azure ML / Azure AI Foundry |
| Secrets / keys / certs | KMS + Secrets Manager + ACM | Key Vault |
| Security posture | GuardDuty + Security Hub | Defender for Cloud |
| IaC | CloudFormation / CDK | Bicep / Terraform |
| Governance | SCP / Control Tower | Azure Policy / Landing Zones |
| Observability | CloudWatch / X-Ray / CloudTrail | Azure Monitor / App Insights / Activity Log |
| Backup vs DR | AWS Backup / Elastic DR | Azure Backup / Site Recovery |
