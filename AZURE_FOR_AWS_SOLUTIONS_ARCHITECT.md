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
