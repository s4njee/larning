# Google Cloud Platform (GCP) for AWS Solutions Architects Study Guide

A practical 15-section guide for architects who already know AWS and want to build strong GCP instincts without starting from zero.

This guide is updated to reflect the Google Cloud architecture and services landscape in 2026. Use the linked official documentation as the current source of truth when a feature, limit, SLA, SKU, or pricing detail matters operationally.

---

## How to Use This Guide

- Study the sections in order if Google Cloud is new to you.
- In each section, anchor on the AWS mental model first, then learn the GCP service names, then internalize the architectural differences.
- Treat the mappings as directional, not literal. Google Cloud and AWS often solve the same problem with different resource hierarchies, network structures, and service boundaries.

### Translation Rules That Matter Early

- An AWS **Organization** maps to a GCP **Organization**.
- An AWS **Account** maps to a GCP **Project**. Projects are the primary resource container and billing unit in GCP.
- A GCP **Folder** acts as an intermediate organizational unit (similar to an AWS OU) to group projects.
- Identity and authentication center on **Google Cloud Identity** and **Google Accounts**, while authorization to GCP resources uses **IAM Policies** bound to resources.
- A major networking difference: AWS VPCs are regional (subnets are AZ-bound); **GCP VPCs are global** (subnets are regional).
- **Amazon CloudWatch** maps across the **Google Cloud Operations Suite** (formerly Stackdriver), including Cloud Logging, Cloud Monitoring, Cloud Trace, and Profiler.

---

## Table of Contents

1. [GCP Foundations: Resource Hierarchy, Billing, Regions, and Zones](#1-gcp-foundations-resource-hierarchy-billing-regions-and-zones)
2. [Identity and Access Management](#2-identity-and-access-management)
3. [Networking, Connectivity, and Edge Delivery](#3-networking-connectivity-and-edge-delivery)
4. [Compute, Virtual Machines, and Scaling](#4-compute-virtual-machines-and-scaling)
5. [Object, Block, and File Storage](#5-object-block-and-file-storage)
6. [Relational Databases](#6-relational-databases)
7. [NoSQL, Cache, and Search](#7-nosql-cache-and-search)
8. [Containers and Kubernetes](#8-containers-and-kubernetes)
9. [Serverless, APIs, and Workflow Orchestration](#9-serverless-apis-and-workflow-orchestration)
10. [Messaging and Event Streaming](#10-messaging-and-event-streaming)
11. [Analytics, Data Lake, and AI/ML](#11-analytics-data-lake-and-aiml)
12. [Observability and Operations](#12-observability-and-operations)
13. [Security, Secrets, and Perimeter Protection](#13-security-secrets-and-perimeter-protection)
14. [Governance, Policy Control, and Cost Management](#14-governance-policy-control-and-cost-management)
15. [DevOps, IaC, Migration, Backup, and Disaster Recovery](#15-devops-iac-migration-backup-and-disaster-recovery)

---

## 1. GCP Foundations: Resource Hierarchy, Billing, Regions, and Zones

### AWS Mental Model

- `AWS Organizations`, `OUs`, `accounts`, `regions`, `availability zones`, `tags`, and the general account boundary for billing and isolation.

### GCP Services and Concepts to Learn

- `Organization`
- `Folders`
- `Projects`
- `Billing Account`
- `Resource Manager`
- `Regions`, `Zones`, and `multi-regions` (e.g., US, EU)

### Key Differences to Internalize

- GCP has a strict, mandatory resource hierarchy: `Organization -> Folders -> Projects -> Resources`. You cannot create a resource without it belonging to a project.
- A **Project** is a far more lightweight boundary than an AWS Account. In GCP, it is common to create many projects (e.g., per service or environment) because they share a central Billing Account and can be easily interconnected via Shared VPCs.
- In GCP, **tags** are key-value pairs managed at the resource level, but GCP also has **labels** (used for querying and filtering) and **tags** (which are managed via Resource Manager and can be used to conditionally apply IAM policies or firewalls).
- Regions and zones exist similarly, but GCP also defines **multi-regions** (geographic areas containing multiple regions, like `us`) which are utilized by storage and database services for out-of-the-box geo-replication.

### Start With These Docs

- [GCP Resource Hierarchy Overview](https://cloud.google.com/resource-manager/docs/cloud-platform-resource-hierarchy)
- [Geography and regions on Google Cloud](https://cloud.google.com/about/locations)
- [GCP Projects overview](https://cloud.google.com/resource-manager/docs/creating-managing-projects)

### Practice

- Design a folder and project structure for a multi-tenant application with `development`, `staging`, and `production` environments.
- Contrast when you would separate components of an application into different Projects vs. different Folders.
- Map an AWS account-per-environment topology to a GCP project-and-folder topology.

---

## 2. Identity and Access Management

### AWS Mental Model

- `IAM users`, `IAM groups`, `IAM roles`, `IAM policies`, `IAM Identity Center (SSO)`, `STS`, and `Organizations SCPs`.

### GCP Services and Concepts to Learn

- `Google Workspace` / `Cloud Identity`
- `GCP IAM` (Google Accounts, Service Accounts, Google Groups)
- `IAM Bindings`, `IAM Policies`, and `IAM Conditions`
- `IAM Roles` (Basic, Predefined, Custom)
- `Service Account User` role (`iam.serviceAccounts.actAs`)
- `Workload Identity Federation` and `Workforce Identity Federation`

### Key Differences to Internalize

- GCP does not have native "IAM Users" created inside the cloud console. All identities (users) must live in a directory, either **Cloud Identity** (Google's IDaaS), **Google Workspace**, or external identities federated via SAML/OIDC. You can use **Workforce Identity Federation** to let users authenticate using an external IdP (like Azure AD/Entra or Okta) without syncing their identities into Google Cloud.
- GCP IAM policies are not attached directly to users; instead, **policies are attached to resources** (Projects, Folders, or individual services like buckets). The policy defines "Who" (member/principal) has "What" (role).
- GCP supports **IAM Conditions**, allowing you to grant access only when specific conditions are met (e.g., specific times of day, IP ranges, or resource naming prefixes).
- A GCP **Service Account** is both an identity (a principal that can be granted roles) and a resource (which other users can be granted permission to use, via the `Service Account User` role).
- GCP uses **Workload Identity Federation** to allow external workloads (like AWS EC2 or GitHub Actions) to impersonate a GCP Service Account without using long-lived security keys.

### Start With These Docs

- [GCP IAM Overview](https://cloud.google.com/iam/docs/overview)
- [Understanding Service Accounts](https://cloud.google.com/iam/docs/service-accounts)
- [Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation)

### Practice

- Write a Terraform block or IAM policy that grants a user group read-only access to a specific Cloud Storage bucket but denies it project-wide.
- Implement an IAM Condition that grants an external contractor access to BigQuery only during standard business hours.
- Explain the security implications of granting a developer the `roles/iam.serviceAccountUser` role.
- Map the concept of an AWS IAM Role assumed by an EC2 instance to a GCP Service Account attached to a Compute Engine instance.

---

## 3. Networking, Connectivity, and Edge Delivery

### AWS Mental Model

- `VPC`, `subnets` (AZ-specific), `route tables`, `internet gateways`, `NAT Gateway`, `security groups`, `NACLs`, `ALB / NLB`, `Route 53`, `CloudFront`, `Direct Connect`, `Transit Gateway`, and `VPC Peering`.

### GCP Services and Concepts to Learn

- `Virtual Private Cloud (VPC)` (Global scope)
- `Subnets` (Regional scope)
- `Cloud Router` and `Cloud NAT`
- `VPC Firewall Rules` and `Firewall Policies`
- `Cloud Load Balancing` (Global External HTTP(S), Regional HTTP(S), Network Load Balancing)
- `Cloud DNS` (including Routing Policies)
- `Cloud CDN`
- `Shared VPC`
- `VPC Network Peering`
- `Network Connectivity Center (NCC)`
- `Cloud Service Mesh` (formerly Anthos Service Mesh)
- `Cloud Interconnect` (Dedicated and Partner)
- `Private Service Connect (PSC)`

### Key Differences to Internalize

- **GCP VPCs are global resources.** When you create a VPC, it spans all regions. Subnets are regional resources, meaning a subnet covers all zones within that region. Instances in different regions can communicate over Google's internal backbone without needing gateways or peering.
- Instead of NACLs and Security Groups, GCP uses **VPC Firewall Rules** applied directly to the network. These rules are target-based, matching instances via network tags, service accounts, or IP ranges.
- **Shared VPC** allows an organization to designate a host project with a VPC and share subnets with service projects. This is Google Cloud's preferred multi-project networking model for internal boundaries.
- For complex hybrid or multi-cloud topologies that mirror AWS Transit Gateway designs, GCP provides **Network Connectivity Center (NCC)**, which manages spokes (VPCs, VPNs, Interconnects) connected to a centralized hub.
- **Cloud Load Balancing** is software-defined and global. A single Anycast external IP address can load balance traffic across multiple regions worldwide, automatically routing users to the closest healthy backend. This acts like AWS Route 53 latency routing combined with an ALB, but simplified into one global service.
- **Private Service Connect (PSC)** allows private consumption of services across different VPC networks and projects, acting as the equivalent to AWS PrivateLink.

### Start With These Docs

- [GCP VPC Network Overview](https://cloud.google.com/vpc/docs/vpc)
- [Shared VPC Overview](https://cloud.google.com/vpc/docs/shared-vpc)
- [Cloud Load Balancing Overview](https://cloud.google.com/load-balancing/docs/load-balancing-overview)
- [VPC Firewall Rules Overview](https://cloud.google.com/firewall/docs/firewalls)

### Practice

- Design a hub-and-spoke topology using a Shared VPC where the hub project controls all egress via Cloud NAT, and spoke projects host the workloads.
- Compare GCP's Global Load Balancing routing logic with AWS Route 53 latency-based routing combined with ALBs.
- Configure a GCP firewall rule that allows port 80/443 traffic only to virtual machines running with a specific Service Account.

---

## 4. Compute, Virtual Machines, and Scaling

### AWS Mental Model

- `EC2`, `AMI`, `Auto Scaling Groups`, `Launch Templates`, `Spot Instances`, `EBS`, and `Instance Store`.

### GCP Services and Concepts to Learn

- `Compute Engine`
- `Machine Images` and `Custom Images`
- `Instance Templates`
- `Managed Instance Groups (MIGs)`
- `Unmanaged Instance Groups`
- `Spot VMs` (replacing Preemptible VMs)
- `Sole-Tenant Nodes`
- `Shielded VMs` and `Confidential Computing`
- `OS Login`
- `Persistent Disk` and `Local SSD`

### Key Differences to Internalize

- Compute Engine instances feature **custom machine types**, letting you tailor the exact CPU and memory configuration for your workload, rather than forcing you into rigid fixed sizes.
- GCP fundamentally handles VM access differently. Instead of relying on static SSH key pairs (like AWS EC2 Key Pairs), GCP uses **OS Login**. This ties SSH access directly to IAM, automatically provisioning temporary SSH keys based on IAM roles and supporting two-factor authentication.
- Compute Engine natively integrates hardware security: **Shielded VMs** offer verifiable integrity against boot- or kernel-level malware, and **Confidential VMs** encrypt data *in use* while being processed in memory (not just at rest or in transit).
- **Managed Instance Groups (MIGs)** handle auto-scaling, auto-healing, and rolling updates. Unlike AWS ASGs, a MIG can be regional, automatically distributing VMs across zones in a region.
- GCP **Spot VMs** have no bidding mechanism. They offer a fixed discount (up to 91% off standard rates) and can be reclaimed by GCP with a 30-second warning. Unlike legacy preemptible VMs, Spot VMs do not have a 24-hour maximum runtime limit.
- **Sole-Tenant Nodes** provide physical isolation on dedicated hardware servers, useful for compliance, licensing (BYOL), and performance predictability.

### Start With These Docs

- [GCP Compute Engine Documentation](https://cloud.google.com/compute/docs)
- [Managed Instance Groups (MIGs) Overview](https://cloud.google.com/compute/docs/instance-groups)
- [Spot VMs Overview](https://cloud.google.com/compute/docs/instances/spot-vms)
- [Persistent Disk Overview](https://cloud.google.com/compute/docs/disks)

### Practice

- Create a regional Managed Instance Group with an auto-scaling policy based on CPU utilization and an auto-healing health check.
- Decide when to use Local SSDs (ephemeral) versus Extreme/SSD Persistent Disks (network storage) for a high-performance database.
- Determine the lifecycle configurations needed to run a batch processing job cost-effectively using Spot VMs.

---

## 5. Object, Block, and File Storage

### AWS Mental Model

- `S3`, `EBS`, `EFS`, `FSx`, and `Glacier / Glacier Deep Archive`.

### GCP Services and Concepts to Learn

- `Cloud Storage (GCS)`
- `GCS Storage Classes` (Standard, Nearline, Coldline, Archive)
- `Persistent Disk (PD)` (Standard, Balanced, SSD, Extreme)
- `Local SSD`
- `Filestore`
- `Bucket Lock` (WORM)
- `Object Lifecycle Management`

### Key Differences to Internalize

- **Cloud Storage (GCS)** is a global unified object store. Unlike S3 buckets, GCS buckets can be regional, dual-regional, or multi-regional.
- GCS does not require you to write a bucket name that is globally unique across all accounts but utilizes projects to namespace access.
- In GCS, all storage classes share the **same API and latency profiles**. Fetching an object from the Archive class takes milliseconds, not hours as with AWS Glacier (though retrieval costs still apply).
- **Persistent Disk (PD)** is network-attached storage. Unlike EBS, a GCP PD can be attached to multiple VMs simultaneously in read-only mode, and Regional PDs offer active-active synchronous replication across two zones in a region.
- **Filestore** is a managed NFS server for file sharing, equivalent to AWS EFS.

### Start With These Docs

- [Cloud Storage Documentation](https://cloud.google.com/storage/docs)
- [GCS Storage Classes](https://cloud.google.com/storage/docs/storage-classes)
- [Persistent Disk Replication Options](https://cloud.google.com/compute/docs/disks/high-availability-regional-persistent-disk)
- [Filestore Overview](https://cloud.google.com/filestore/docs/reference/rest)

### Practice

- Configure a GCS bucket with a lifecycle policy that transitions objects to Coldline after 30 days and deletes them after 365 days.
- Design a disaster recovery storage setup using a dual-regional GCS bucket.
- Architect a high-availability application using Regional Persistent Disks to enable instant failover of block storage between zones.

---

## 6. Relational Databases

### AWS Mental Model

- `RDS`, `Aurora`, and self-managed databases on `EC2`.

### GCP Services and Concepts to Learn

- `Cloud SQL`
- `AlloyDB for PostgreSQL`
- `Cloud Spanner`
- `Bare Metal Solution`

### Key Differences to Internalize

- **Cloud SQL** is the direct equivalent to AWS RDS, offering managed MySQL, PostgreSQL, and SQL Server.
- **AlloyDB** is Google's high-performance, Postgres-compatible database engine, comparable to AWS Aurora Postgres. It utilizes a separate compute and storage architecture, offering massive scale, fast replication, and built-in vector search optimization.
- **Cloud Spanner** is GCP’s premier database offering: a fully managed, enterprise-grade, **globally distributed, strongly consistent** relational database. It scales horizontally to thousands of nodes while maintaining ACID transactions across continents, using atomic clocks and GPS receivers (TrueTime) to coordinate transactions. There is no direct equivalent in AWS.
- **Bare Metal Solution** provides dedicated hardware to run legacy workloads (like Oracle databases) with low latency access to GCP services.

### Start With These Docs

- [Cloud SQL Overview](https://cloud.google.com/sql/docs)
- [AlloyDB for PostgreSQL Overview](https://cloud.google.com/alloydb/docs/overview)
- [Cloud Spanner Overview](https://cloud.google.com/spanner/docs/overview)
- [TrueTime and External Consistency in Spanner](https://cloud.google.com/spanner/docs/truetime-external-consistency)

### Practice

- Contrast the architectural differences between deploying PostgreSQL on Cloud SQL, AlloyDB, and Cloud Spanner.
- Analyze when an application requires Cloud Spanner over a traditional primary-replica relational database.
- Design a high-availability failover topology for a Cloud SQL database instance across two zones.

---

## 7. NoSQL, Cache, and Search

### AWS Mental Model

- `DynamoDB`, `ElastiCache (Redis/Memcached)`, `DocumentDB`, `Keyspaces`, and `OpenSearch`.

### GCP Services and Concepts to Learn

- `Firestore` (Datastore mode and Native mode)
- `Cloud Bigtable`
- `Memorystore` (for Redis and Memcached)
- `Vertex AI Search` (formerly Enterprise Search)

### Key Differences to Internalize

- **Firestore** is a serverless document database (similar to DynamoDB or DocumentDB) offering sub-second queries, real-time sync, and offline support. It runs in two modes: Native (for mobile/web) and Datastore (for high-throughput backend services).
- **Cloud Bigtable** is GCP's high-performance, low-latency NoSQL database designed for large analytical and operational workloads (billions of rows, petabytes of data). It is the same engine that powers Google Search and Maps, and maps to AWS Keyspaces or wide-column DynamoDB patterns.
- **Memorystore** is a fully managed in-memory cache service compatible with Redis and Memcached, matching AWS ElastiCache.
- **Vertex AI Search** provides out-of-the-box semantic search, retrieval-augmented generation (RAG), and enterprise search capabilities.

### Start With These Docs

- [Firestore Documentation](https://cloud.google.com/firestore/docs)
- [Cloud Bigtable Overview](https://cloud.google.com/bigtable/docs/overview)
- [Memorystore for Redis Overview](https://cloud.google.com/memorystore/docs/redis)

### Practice

- Design a Firestore schema utilizing subcollections and outline how indexes are generated.
- Determine the correct partition key strategy for a Cloud Bigtable instance to prevent hotspotting.
- Choose between Firestore, Bigtable, and Memorystore for a real-time gaming leaderboard application.

---

## 8. Containers and Kubernetes

### AWS Mental Model

- `ECR`, `ECS`, `EKS`, `Fargate`, and `App Mesh`.

### GCP Services and Concepts to Learn

- `Artifact Registry`
- `Google Kubernetes Engine (GKE)` (Standard and Autopilot)
- `GKE Enterprise` (formerly Anthos) and `Fleet Management`
- `VPC-native clusters`
- `Cloud Run`
- `Service Directory`

### Key Differences to Internalize

- **GKE** is widely considered the industry-leading managed Kubernetes service. It offers a fully managed control plane and a choice between **GKE Standard** (you manage the worker nodes) and **GKE Autopilot** (Google provisions, configures, and scales the nodes based on your Pod specs, charging only for running pods).
- In GCP networking, **VPC-native clusters** are the modern standard. They use alias IPs so that pod IP addresses are natively routable within the VPC, entirely distinct from legacy routes-based clusters.
- For hybrid or multi-cloud scenarios, **GKE Enterprise** (formerly Anthos) provides a consistent Kubernetes management layer. It uses **Fleet Management** to group and apply policies (Config Sync) across clusters in GCP, AWS, Azure, and on-premises environments.
- **Cloud Run** is GCP's premier container abstraction: a serverless compute platform that runs stateless containers, scaling them from zero to thousands of instances automatically. It handles all HTTPS routing, TLS certificates, and scales based on concurrent requests. It is the GCP equivalent of running AWS ECS with Fargate, but with far less configuration overhead.
- **Artifact Registry** is the evolution of Container Registry, supporting Docker images, Maven, npm, Python packages, and Helm charts, equivalent to AWS ECR.

### Start With These Docs

- [Google Kubernetes Engine (GKE) Documentation](https://cloud.google.com/kubernetes-engine/docs)
- [GKE Autopilot vs. Standard](https://cloud.google.com/kubernetes-engine/docs/concepts/autopilot-overview)
- [Cloud Run Overview](https://cloud.google.com/run/docs/overview)
- [Artifact Registry Overview](https://cloud.google.com/artifact-registry/docs)

### Practice

- Write a Dockerfile and deploy it to Cloud Run, configuring it to scale to zero when idle and setting custom concurrency limits.
- Deploy an application on GKE Autopilot using Workload Identity to grant the Kubernetes service account access to a GCP bucket.
- Compare the operational complexity of deploying a microservice on Cloud Run versus GKE Autopilot.

---

## 9. Serverless, APIs, and Workflow Orchestration

### AWS Mental Model

- `Lambda`, `API Gateway`, and `Step Functions`.

### GCP Services and Concepts to Learn

- `Cloud Functions` (2nd gen)
- `Cloud Run` (as a serverless backend API option)
- `API Gateway` and `Apigee`
- `Workflows`

### Key Differences to Internalize

- **Cloud Functions (2nd gen)** is built on top of Cloud Run and Eventarc, running on standard container runtimes. This means it supports larger memory sizes (up to 32GB), longer execution times (up to 60 minutes for HTTP requests), and handles multiple concurrent requests on a single instance (unlike AWS Lambda's 1-invocation-per-instance model).
- For complex API gateways, GCP offers **Apigee** (an enterprise-grade API management platform) alongside the simpler **API Gateway** (for securing and managing simple Cloud Run and Cloud Functions endpoints).
- **Workflows** is Google's serverless state machine and orchestration engine, equivalent to AWS Step Functions, utilizing YAML or JSON to define steps, retries, and error handling.

### Start With These Docs

- [Cloud Functions (2nd gen) Overview](https://cloud.google.com/functions/docs/2nd-gen/overview)
- [Workflows Overview](https://cloud.google.com/workflows/docs/overview)
- [Apigee API Management](https://cloud.google.com/apigee/docs/api-platform/get-started/what-apigee)

### Practice

- Build a serverless workflow using GCP Workflows that calls a Cloud Function, parses the JSON response, and stores the result in Firestore.
- Configure a Cloud Function to run with a minimum instance count of 1 to eliminate cold-start latency.
- Diagram the API Gateway placement in front of a multi-project Cloud Run microservice mesh.

---

## 10. Messaging and Event Streaming

### AWS Mental Model

- `SQS`, `SNS`, `EventBridge`, `Kinesis Data Streams`, and `MSK`.

### GCP Services and Concepts to Learn

- `Pub/Sub`
- `Pub/Sub Lite`
- `Eventarc`

### Key Differences to Internalize

- **Pub/Sub** is a global, horizontal, real-time messaging service that combines the use cases of both AWS SQS (queuing) and SNS (pub/sub). Publishers send messages to a topic, and subscribers pull or receive push messages from subscriptions. There is no infrastructure to provision or scale.
- **Pub/Sub Lite** is a lower-cost, zonal alternative to Pub/Sub designed for high-volume log ingestion where ordering and partition management can be handled by the client (similar to AWS Kinesis).
- **Eventarc** allows you to route events from Google Cloud services, custom sources, and SaaS apps directly to Cloud Run, Cloud Functions, or GKE, acting as the direct equivalent of AWS EventBridge.

### Start With These Docs

- [Pub/Sub Overview](https://cloud.google.com/pubsub/docs/overview)
- [Eventarc Overview](https://cloud.google.com/eventarc/docs/overview)
- [Pub/Sub vs. Pub/Sub Lite](https://cloud.google.com/pubsub/docs/choosing-pubsub-or-lite)

### Practice

- Create a Pub/Sub topic with two subscriptions: one push subscription pointing to a Cloud Run endpoint, and one pull subscription for manual worker processing.
- Configure Eventarc to trigger a Cloud Function whenever a new object is finalized in a Cloud Storage bucket.
- Explain how message ordering and dead-letter queues are configured in GCP Pub/Sub.

---

## 11. Analytics, Data Lake, and AI/ML

### AWS Mental Model

- `Athena`, `Glue`, `EMR`, `Redshift`, `Kinesis Firehose`, `SageMaker`, and various AWS AI services.

### GCP Services and Concepts to Learn

- `BigQuery`
- `BigQuery Omni` and `BigLake`
- `Dataflow`
- `Dataproc`
- `Data Fusion`
- `Vertex AI`
- `Vertex AI Studio` (including Gemini access)

### Key Differences to Internalize

- **BigQuery** is Google Cloud's crown jewel. It is a serverless, highly scalable **data warehouse and analytics engine** that separates compute and storage. It allows SQL queries across petabytes of data in seconds. It combines the use cases of AWS Redshift (warehouse) and Athena (ad-hoc SQL querying) with zero management overhead.
- **BigQuery Omni** and **BigLake** enable multi-cloud analytics. You can run BigQuery SQL over data residing in AWS S3 or Azure Blob Storage *without* moving or copying the data into GCP.
- **Dataflow** is a managed service for executing Apache Beam pipelines for unified stream and batch data processing, equivalent to AWS Glue/Kinesis Analytics.
- **Dataproc** is a managed Spark and Hadoop service, comparable to AWS EMR.
- **Vertex AI** is GCP's end-to-end machine learning platform. It unifies ML models, feature stores, pipelines, training, and model deployment (comparable to AWS SageMaker). In 2026, it serves as the central hub for deploying foundation models (like Gemini) via APIs and fine-tuning.

### Start With These Docs

- [BigQuery Documentation](https://cloud.google.com/bigquery/docs)
- [Vertex AI Platform Overview](https://cloud.google.com/vertex-ai/docs/start/introduction-unified-platform)
- [Cloud Dataflow Overview](https://cloud.google.com/dataflow/docs/guides/concepts)
- [Cloud Dataproc Overview](https://cloud.google.com/dataproc/docs/concepts)

### Practice

- Run a BigQuery SQL query analyzing a public dataset, analyzing how slot allocation and partitioned tables affect query costs.
- Design an ingestion pipeline using Cloud Pub/Sub, Cloud Dataflow, and BigQuery.
- Deploy a Gemini model endpoint in Vertex AI, configuring system instructions and safety settings.

---

## 12. Observability and Operations

### AWS Mental Model

- `CloudWatch Logs / Metrics`, `X-Ray`, `CloudTrail`, and `Systems Manager (SSM)`.

### GCP Services and Concepts to Learn

- `Cloud Logging` (including `Log Routers` and `Log Sinks`)
- `Cloud Monitoring`
- `Cloud Trace`
- `Cloud Profiler`
- `Error Reporting`
- `VM Manager`

### Key Differences to Internalize

- GCP's operations suite is unified under the **Google Cloud Operations Suite** (formerly Stackdriver).
- **Cloud Logging** is exceptionally powerful: it automatically captures all standard output/error from serverless runtimes, VMs, and Kubernetes containers without requiring log agents in many cases. Logs are indexed and searchable using the Logging query language.
- A core operational pattern in GCP uses **Log Routers** and **Log Sinks** to export logs. You route security logs to Pub/Sub (for external SIEM integration) or export audit and application logs to BigQuery (for long-term retention and SQL analysis).
- **Cloud Monitoring** collects metrics, dashboards, and alerts. It integrates natively with GKE and Compute Engine.
- **Cloud Trace** and **Cloud Profiler** provide out-of-the-box distributed tracing and continuous application profiling to optimize code execution latency and memory usage.
- **Error Reporting** automatically aggregates runtime exceptions from your applications, groups them, and alerts you when new bugs occur.

### Start With These Docs

- [Google Cloud Operations Suite Overview](https://cloud.google.com/products/operations)
- [Cloud Logging Overview](https://cloud.google.com/logging/docs/overview)
- [Cloud Monitoring Overview](https://cloud.google.com/monitoring/docs/overview)
- [Error Reporting Overview](https://cloud.google.com/error-reporting/docs)

### Practice

- Write a Cloud Logging query to filter errors in a specific Cloud Run service and create a metric-based alert from it.
- Set up an uptime check in Cloud Monitoring that pings an external load balancer and sends notifications on failure.
- Instrument a Go or Node.js application to send trace data to Cloud Trace.

---

## 13. Security, Secrets, and Perimeter Protection

### AWS Mental Model

- `KMS`, `Secrets Manager`, `GuardDuty`, `Security Hub`, `WAF`, and `Shield`.

### GCP Services and Concepts to Learn

- `Identity-Aware Proxy (IAP)`
- `Cloud KMS`
- `Secret Manager`
- `Cloud Armor`
- `Security Command Center (SCC)`
- `VPC Service Controls (VPC SC)`

### Key Differences to Internalize

- **Identity-Aware Proxy (IAP)** is the cornerstone of Google's BeyondCorp (Zero Trust) model. It allows employees to securely access internal web apps or SSH/RDP into VMs from the public internet based on their identity and device context, completely eliminating the need for traditional VPNs.
- **Cloud KMS** handles cryptographic key management (symmetric/asymmetric keys, signing, rotation). It integrates seamlessly with GCP services for Customer-Managed Encryption Keys (CMEK).
- **Secret Manager** is GCP's vault for API keys, passwords, and certificates, matching AWS Secrets Manager.
- **Cloud Armor** is Google's WAF and DDoS protection service. It runs at the edge of Google's global network, allowing you to filter incoming traffic to Cloud Load Balancers before it reaches your backend instances.
- **Security Command Center (SCC)** provides security posture management, vulnerability detection, and threat monitoring (similar to AWS Security Hub + GuardDuty).
- **VPC Service Controls (VPC SC)** is a unique GCP security feature. It allows you to define a security perimeter around Google-managed resources (like Cloud Storage, BigQuery) to prevent data exfiltration. Using ingress/egress rules and Access Levels, it ensures data cannot leave your designated projects even if a user has valid IAM credentials.

### Start With These Docs

- [GCP Security Documentation](https://cloud.google.com/security)
- [Secret Manager Overview](https://cloud.google.com/secret-manager/docs/overview)
- [Cloud Armor Overview](https://cloud.google.com/armor/docs/cloud-armor-overview)
- [VPC Service Controls Overview](https://cloud.google.com/vpc-service-controls/docs/overview)

### Practice

- Design a secure storage pipeline where a Cloud Storage bucket is encrypted using a Customer-Managed Encryption Key (CMEK) managed in Cloud KMS.
- Define a Cloud Armor security policy that blocks traffic from specific geographic regions and protects against SQL injection.
- Configure a VPC Service Controls perimeter to protect a critical BigQuery dataset from exfiltration.

---

## 14. Governance, Policy Control, and Cost Management

### AWS Mental Model

- `Organizations SCPs`, `Config`, `Trusted Advisor`, `Cost Explorer`, and `Budgets`.

### GCP Services and Concepts to Learn

- `Organization Policy Service`
- `Assured Workloads`
- `Recommender`
- `Cloud Billing`
- `Resource Quotas`
- `Asset Inventory`

### Key Differences to Internalize

- **Organization Policy Service** provides centralized, programmatic control over your organization's resources. Unlike IAM (which restricts *who* can do things), Org Policies restrict *what* can be done (e.g., preventing external IP addresses on VMs, enforcing key rotation, or restricting resource creation to specific regions). This maps to AWS SCPs.
- **Assured Workloads** is crucial for compliance in regulated industries. It allows you to create specialized folders that automatically enforce data residency and compliance regimes (like FedRAMP, HIPAA, or GDPR) across all underlying resources.
- **Recommender** is an active intelligence engine that automatically analyzes your resource usage to suggest VM sizing optimizations, detect idle disks, identify insecure IAM permissions, and find cost savings.
- **Resource Quotas** are strictly enforced limits to prevent resource exfiltration and cost overruns. You must request quota increases via the console for large deployments.

### Start With These Docs

- [GCP Organization Policy Service](https://cloud.google.com/resource-manager/docs/organization-policy/overview)
- [GCP Recommender Overview](https://cloud.google.com/recommender/docs/recommender-overview)
- [Understanding GCP Billing](https://cloud.google.com/billing/docs)

### Practice

- Implement an Organization Policy that restricts all future VM instances to running in the `us-central1` and `us-east1` regions.
- Set up a billing alert budget that triggers a Pub/Sub topic to notify a Slack webhook when costs reach 80% of the target.
- Query your active cloud resources using Cloud Asset Inventory to identify unencrypted storage buckets.

---

## 15. DevOps, IaC, Migration, Backup, and Disaster Recovery

### AWS Mental Model

- `CloudFormation / CDK`, `CodePipeline`, `CodeBuild`, `CodeDeploy`, `Migration Hub`, `DMS`, `AWS Backup`, and `Elastic Disaster Recovery`.

### GCP Services and Concepts to Learn

- `Terraform` (GCP's de facto IaC standard)
- `Deployment Manager` (First-party IaC, but less common)
- `Cloud Build`
- `Cloud Deploy`
- `Database Migration Service (DMS)`
- `Backup and DR Service`

### Key Differences to Internalize

- While Google has **Deployment Manager**, **Terraform** is the undisputed de facto industry standard for GCP Infrastructure as Code. Google actively collaborates with HashiCorp to maintain the GCP Terraform provider.
- **Cloud Build** is a serverless CI/CD platform that executes builds as Docker containers, mapping to AWS CodeBuild.
- **Cloud Deploy** handles managed continuous delivery to target environments like GKE, Cloud Run, and Anthos, providing built-in release gates, approvals, and canary rollouts.
- **Backup and DR Service** provides centralized management of application, database, and VM backup states, matching AWS Backup.

### Start With These Docs

- [Terraform on Google Cloud](https://cloud.google.com/docs/terraform)
- [Cloud Build Documentation](https://cloud.google.com/build/docs)
- [Cloud Deploy Overview](https://cloud.google.com/deploy/docs/overview)
- [Backup and DR Service Overview](https://cloud.google.com/backup-disaster-recovery/docs)

### Practice

- Write a Terraform configuration that deploys a Cloud Run service, its corresponding service account, and a Cloud Storage bucket, adhering to least-privilege IAM permissions.
- Create a Cloud Build configuration file (`cloudbuild.yaml`) that triggers on a git push, builds a container image, pushes it to Artifact Registry, and deploys it to Cloud Run.
- Design a backup and restore schedule for a multi-region database setup using Backup and DR Service.
