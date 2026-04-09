# Kubernetes Security Study Guide

A practical, production-focused guide to Kubernetes security. The goal is not to memorize every API flag or every compliance buzzword. The goal is to understand how Kubernetes security layers fit together, where the common failure modes are, and how to design a cluster that is defensible in production.

As of April 9, 2026, the upstream Kubernetes documentation site lists `v1.35` as the current docs version. This guide assumes current, v1.35-era guidance and calls out places where managed clusters or older versions may behave differently.

The main theme of Kubernetes security is this: there is no single control that makes a cluster secure. Real security comes from stacking identity, authorization, workload hardening, network isolation, secrets protection, auditability, and operational discipline so that one mistake does not become total cluster compromise.

---

## Table of Contents

1. [Phase 1: Core Security Model](#phase-1-core-security-model)
2. [Phase 2: Authentication and Access Control](#phase-2-authentication-and-access-control)
3. [Phase 3: Network and Multi-Tenancy Security](#phase-3-network-and-multi-tenancy-security)
4. [Phase 4: Workload and Container Security](#phase-4-workload-and-container-security)
5. [Phase 5: Secrets and Sensitive Data Protection](#phase-5-secrets-and-sensitive-data-protection)
6. [Phase 6: Audit, Detection, and Response](#phase-6-audit-detection-and-response)
7. [Phase 7: Important Third-Party Security Topics](#phase-7-important-third-party-security-topics)
8. [Phase 8: Production Hardening Checklist](#phase-8-production-hardening-checklist)
9. [Hands-On Labs](#hands-on-labs)
10. [What Good Looks Like in Production](#what-good-looks-like-in-production)

---

## Phase 1: Core Security Model

### 1.1 The Four Big Security Planes in Kubernetes

- **Cluster access plane**: Who can talk to the Kubernetes API, and how they authenticate.
  - This is where OIDC, certificates, cloud-provider identity integrations, kubeconfig handling, and API endpoint exposure matter most; docs: [Controlling Access to the Kubernetes API](https://kubernetes.io/docs/concepts/security/controlling-access/), [Authenticating](https://kubernetes.io/docs/reference/access-authn-authz/authentication/).
- **Authorization and policy plane**: What an authenticated identity is allowed to do.
  - This is where RBAC, admission control, and policy engines determine whether a request should be allowed at all; docs: [Using RBAC Authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/), [RBAC Good Practices](https://kubernetes.io/docs/concepts/security/rbac-good-practices/).
- **Workload isolation plane**: What a Pod can do after it is running.
  - This is where Pod Security Standards, `securityContext`, seccomp, AppArmor, SELinux, Linux capabilities, and privileged containers matter; docs: [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/), [Linux kernel security constraints for Pods and containers](https://kubernetes.io/docs/concepts/security/linux-kernel-security-constraints/), [Configure a Security Context for a Pod or Container](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/).
- **Data and observability plane**: How secrets, audit trails, and evidence are handled.
  - This is where Secrets, encryption at rest, external secret stores, audit policies, and log pipelines matter; docs: [Secrets](https://kubernetes.io/docs/concepts/configuration/secret/), [Good practices for Kubernetes Secrets](https://kubernetes.io/docs/concepts/security/secrets-good-practices/), [Auditing](https://kubernetes.io/docs/tasks/debug/debug-cluster/audit/).

### 1.2 Kubernetes Security Is Mostly About Blast Radius

- **Assume a credential can leak**
  - Design so a stolen developer kubeconfig, compromised Pod token, or leaked CI credential does not become full-cluster admin.
- **Assume a Pod can be exploited**
  - Design so one vulnerable app container cannot trivially read every Secret, reach every Pod, or gain node-level access.
- **Assume a node can be partially compromised**
  - Design so node compromise does not silently bypass your main control path or expose cleartext data unnecessarily.
- **Assume mistakes will happen**
  - Use layered controls so a bad manifest, permissive RoleBinding, or forgotten namespace policy is caught somewhere else.

### 1.3 The Most Important Mindset Shift

- **Kubernetes defaults are often functional, not production-secure**
  - Pods can usually talk freely unless you add network policies. Teams often over-grant RBAC. Secrets are just base64-encoded unless you add real encryption controls. Service accounts are easy to misuse. Production security is mostly about intentionally tightening defaults.
- **The API server is the choke point you want to preserve**
  - Authentication, authorization, admission, and audit logging all happen at the API server. Anything that bypasses it is disproportionately risky; docs: [Kubernetes API Server Bypass Risks](https://kubernetes.io/docs/concepts/security/api-server-bypass-risks/).

### 1.4 Foundation Docs You Should Know Cold

- [Security Checklist](https://kubernetes.io/docs/concepts/security/security-checklist/)
- [Application Security Checklist](https://kubernetes.io/docs/concepts/security/application-security-checklist/)
- [Cloud Native Security](https://kubernetes.io/docs/concepts/security/overview/)
- [Multi-tenancy](https://kubernetes.io/docs/concepts/security/multi-tenancy/)

---

## Phase 2: Authentication and Access Control

### 2.1 How Kubernetes Secures API Access

Every request to the Kubernetes API goes through a chain:

1. **Authentication**: who are you?
2. **Authorization**: what are you allowed to do?
3. **Admission**: should this specific object or change be accepted?
4. **Audit**: what happened, and who did it?

That sequence is the backbone of Kubernetes security; docs: [Controlling Access to the Kubernetes API](https://kubernetes.io/docs/concepts/security/controlling-access/).

### 2.2 Authentication Methods You Must Understand

- **OIDC / external identity provider**
  - Best default for human user access in production. Kubernetes upstream explicitly recommends using external authentication such as OIDC for production clusters with multiple human users; docs: [Hardening Guide - Authentication Mechanisms](https://kubernetes.io/docs/concepts/security/hardening-guide/authentication-mechanisms/), [Authenticating](https://kubernetes.io/docs/reference/access-authn-authz/authentication/).
- **X.509 client certificates**
  - Important for system components and occasionally for tightly controlled admin access, but awkward for broad user auth because revocation and lifecycle management are harder; docs: [Hardening Guide - Authentication Mechanisms](https://kubernetes.io/docs/concepts/security/hardening-guide/authentication-mechanisms/), [PKI certificates and requirements](https://kubernetes.io/docs/setup/best-practices/certificates/), [Issue a Certificate for a Kubernetes API Client Using A CertificateSigningRequest](https://kubernetes.io/docs/tasks/tls/certificate-issue-client-csr/).
- **Service account tokens**
  - Intended for workloads, not humans. Modern Kubernetes prefers short-lived projected tokens from the `TokenRequest` API, not legacy long-lived token Secrets; docs: [Service Accounts](https://kubernetes.io/docs/concepts/security/service-accounts/), [Configure Service Accounts for Pods](https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/), [Hardening Guide - Authentication Mechanisms](https://kubernetes.io/docs/concepts/security/hardening-guide/authentication-mechanisms/).
- **Webhook or authenticating proxy**
  - Useful in specialized environments, but add infrastructure and trust complexity. These are not usually the first choice unless your platform already depends on them; docs: [Authenticating](https://kubernetes.io/docs/reference/access-authn-authz/authentication/), [Hardening Guide - Authentication Mechanisms](https://kubernetes.io/docs/concepts/security/hardening-guide/authentication-mechanisms/).

### 2.3 OIDC: The Main Production Pattern for Human Access

- **What it is**
  - Kubernetes trusts tokens issued by an external identity provider such as Okta, Microsoft Entra ID, Google, Dex, or another OIDC-capable IdP.
- **Why it matters**
  - It centralizes identity lifecycle, supports MFA and corporate SSO, and avoids inventing a separate human-user credential system just for Kubernetes.
- **What to study**
  - Token issuer configuration
  - Audience and claim mapping
  - Group-based authorization
  - Short token lifetimes
  - How `kubectl` gets credentials through exec plugins or managed provider tooling
- **Hardening points**
  - Keep OIDC support components isolated if they run in-cluster.
  - Prefer short-lived tokens.
  - Be aware that some managed Kubernetes offerings constrain which OIDC flows or providers you can use; docs: [Hardening Guide - Authentication Mechanisms](https://kubernetes.io/docs/concepts/security/hardening-guide/authentication-mechanisms/).

### 2.4 Certificates: Important, but Usually Not Your Main Human Auth Strategy

- **Where certificates shine**
  - Control-plane internals
  - Kubelet identity
  - Bootstrap and rotation workflows
  - Emergency or tightly controlled admin access
- **Where certificates are weak**
  - Individual revocation is poor
  - Group membership is effectively baked into the cert
  - Private key handling is operationally brittle
  - Distribution and tracking get painful as human user count grows
- **What to know**
  - The CSR API
  - Manual and kubeadm certificate workflows
  - Certificate rotation implications
  - Why certificate issuance rights are security-sensitive RBAC permissions; docs: [PKI certificates and requirements](https://kubernetes.io/docs/setup/best-practices/certificates/), [Issue a Certificate for a Kubernetes API Client Using A CertificateSigningRequest](https://kubernetes.io/docs/tasks/tls/certificate-issue-client-csr/), [RBAC Good Practices](https://kubernetes.io/docs/concepts/security/rbac-good-practices/).

### 2.5 Cloud Provider IAM and Managed Cluster Access

This is one of the most practically important areas in production. In managed clusters, there are usually two related but separate identity problems:

1. **How humans get cluster access**
2. **How workloads in Pods get cloud API access**

Do not blur those together.

#### AWS / EKS

- **Human access to the cluster**
  - EKS cluster access is increasingly centered around access entries and AWS IAM identities rather than legacy `aws-auth` management patterns; docs: [Change authentication mode to use access entries](https://docs.aws.amazon.com/eks/latest/userguide/setting-up-access-entries.html).
- **Workload access to AWS APIs**
  - IAM Roles for Service Accounts (IRSA) lets Pods use projected service account OIDC tokens to assume IAM roles without static AWS keys in Secrets; docs: [IAM roles for service accounts](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html).
- **Key study point**
  - IRSA improves credential isolation, but AWS explicitly notes that containers are not a security boundary. Node compromise or privileged Pod placement still matters.

#### Google Cloud / GKE

- **Human access to the cluster**
  - GKE supports external identity provider integration and related identity federation workflows for cluster auth; docs: [Use external identity providers to authenticate to GKE](https://cloud.google.com/kubernetes-engine/docs/how-to/oidc).
- **Workload access to Google Cloud APIs**
  - Workload Identity Federation for GKE is the recommended path instead of shipping service account keys into Pods; docs: [About Workload Identity Federation for GKE](https://cloud.google.com/kubernetes-engine/docs/concepts/workload-identity), [Authenticate to Google Cloud APIs from GKE workloads](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity).
- **Key study point**
  - Understand the separation between Kubernetes ServiceAccounts and Google IAM service accounts, and study the limitations around `hostNetwork: true` and metadata access.

#### Azure / AKS

- **Human access to the cluster**
  - AKS commonly uses AKS-managed Microsoft Entra integration for authentication to the cluster; docs: [Enable AKS-managed Microsoft Entra integration](https://learn.microsoft.com/en-us/azure/aks/enable-authentication-microsoft-entra-id).
- **Workload access to Azure APIs**
  - Microsoft Entra Workload ID federates Kubernetes service account tokens to Azure identities for Pods that need cloud access; docs: [Microsoft Entra Workload ID on AKS](https://learn.microsoft.com/en-us/azure/aks/workload-identity-overview), [Create an OIDC provider for AKS](https://learn.microsoft.com/en-us/azure/aks/use-oidc-issuer).
- **Key study point**
  - AKS identity design is often a combination of Microsoft Entra for users, Kubernetes RBAC for cluster authorization, and workload identity for Pods.

### 2.6 RBAC: The Most Important Authorization Model to Master

- **RBAC decides what an authenticated identity can do**
  - Learn `Role`, `ClusterRole`, `RoleBinding`, and `ClusterRoleBinding` thoroughly; docs: [Using RBAC Authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/).
- **Least privilege is the whole game**
  - Avoid broad verbs, broad resources, and cluster-wide grants unless you have a specific reason.
- **Namespace scoping is your friend**
  - Many teams accidentally make every operator a cluster administrator because scoping work correctly takes more effort.
- **Groups beat per-user bindings**
  - Map users to groups in your IdP, then bind groups to RBAC roles.
- **Separate human and workload permissions**
  - A CI system, controller, developer, and support engineer should not all share the same role shape.

### 2.7 RBAC Good Practices You Need to Internalize

Kubernetes upstream has an unusually useful RBAC good-practices page. Study it closely; docs: [Role Based Access Control Good Practices](https://kubernetes.io/docs/concepts/security/rbac-good-practices/).

The high-value lessons are:

- **Avoid `system:masters`**
  - Upstream explicitly warns that membership in `system:masters` bypasses all RBAC checks and even authorization webhooks.
- **Avoid wildcard permissions**
  - `*` on resources or verbs is an easy way to create accidental future privilege.
- **Treat Secrets read access as highly privileged**
  - If you can read Secrets in a namespace, you can often pivot into workload or cloud credentials.
- **Treat workload creation as privileged**
  - If you can create Pods, you can often mount service account tokens, host paths, or other sensitive assets depending on cluster policy.
- **Treat certificate issuance, token request, bind, escalate, and impersonate as dangerous**
  - These are classic RBAC escalation paths.
- **Review permissions periodically**
  - RBAC debt accumulates silently.

### 2.8 Service Accounts: Critical and Frequently Misused

- **Every workload identity should be intentional**
  - Create purpose-specific ServiceAccounts instead of letting everything run as namespace default.
- **Disable token automount where not needed**
  - Many workloads do not need to call the Kubernetes API at all; docs: [Configure Service Accounts for Pods](https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/).
- **Prefer projected, short-lived tokens**
  - Modern clusters use TokenRequest-backed projected tokens with bounded lifetimes, not legacy long-lived token Secrets; docs: [Configure Service Accounts for Pods](https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/), [Hardening Guide - Authentication Mechanisms](https://kubernetes.io/docs/concepts/security/hardening-guide/authentication-mechanisms/).
- **Use workload identity federation when cloud APIs are needed**
  - Do not store long-lived AWS, GCP, or Azure credentials in Kubernetes Secrets if the platform supports federation.

### 2.9 kubeconfig Security Matters More Than Many Teams Realize

- **A kubeconfig is often a credential, not just a config file**
  - It may contain client certificates, bearer tokens, or exec-based auth flows.
- **Treat kubeconfigs like secrets**
  - Store them carefully, prefer short-lived auth, and avoid leaving admin kubeconfigs on laptops or CI agents.
- **Segment admin access**
  - Break-glass admin credentials should be rare, heavily audited, and not your day-to-day workflow.

### 2.10 Admission Control Is Where Security Policy Becomes Enforceable

- **Admission is the last checkpoint before an object is persisted**
  - Authentication tells Kubernetes who you are, RBAC tells it what verbs you may attempt, and admission decides whether this specific object shape is acceptable; docs: [Admission Controllers](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/), [Controlling Access to the Kubernetes API](https://kubernetes.io/docs/concepts/security/controlling-access/).
- **Native admission already covers important security cases**
  - Pod Security Admission is the most obvious example, but admission also matters for defaulting, validation, and cluster-wide policy enforcement.
- **ValidatingAdmissionPolicy is worth learning**
  - It gives Kubernetes-native validation logic without always requiring an external webhook deployment; docs: [Validating Admission Policy](https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/).
- **Webhook-based admission is powerful and risky**
  - If you depend on external admission webhooks for security, those webhooks become part of your control plane reliability and trust model.

---

## Phase 3: Network and Multi-Tenancy Security

### 3.1 Network Policies Are the Main Native East-West Isolation Control

- **What they do**
  - Restrict which Pods can talk to which other Pods or CIDRs for ingress and egress; docs: [Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/).
- **What many people miss**
  - Policies are additive, and both the source egress side and destination ingress side must allow the flow.
- **The most important operational caveat**
  - NetworkPolicy objects do nothing unless your CNI actually enforces them.
- **The most common production pattern**
  - Start with default-deny, then add specific allow rules for DNS, app-to-app traffic, ingress controllers, and required external egress.

### 3.2 What to Learn About NetworkPolicy

- Pod selectors and namespace selectors
- Ingress vs egress policies
- Default deny patterns
- DNS allowance
- Namespace label trust assumptions
- How your chosen CNI implements enforcement

### 3.3 North-South Security Is Not Solved by NetworkPolicy Alone

- **Ingress, Gateway, and load balancers are security boundaries too**
  - You need TLS termination strategy, client IP handling, WAF strategy, and rate limiting thinking.
- **Separate public and private entry paths**
  - Public internet traffic should not share the same route or policy assumptions as internal admin traffic.
- **Use mTLS where appropriate**
  - Native Kubernetes does not give you mesh-style mutual TLS for service-to-service traffic by default.

### 3.4 Multi-Tenancy Changes the Security Model

- **By default, Pods can communicate broadly**
  - Upstream multi-tenancy guidance recommends default deny network policies plus specific DNS allowances in stricter tenant isolation scenarios; docs: [Multi-tenancy](https://kubernetes.io/docs/concepts/security/multi-tenancy/).
- **Namespace isolation is useful, but not absolute**
  - Namespaces are a control-plane partitioning tool, not a perfect hard boundary.
- **You need multiple isolation layers**
  - RBAC
  - network policy
  - quotas and limits
  - node isolation
  - storage isolation
  - workload hardening
- **Not every cluster should be multi-tenant**
  - Sometimes the right answer is more clusters, not more policy complexity.

### 3.5 Common Network Security Mistakes

- **No default-deny policies**
- **Allowing unrestricted egress everywhere**
- **Using a CNI that supports NetworkPolicy but never testing enforcement**
- **Relying on namespace names instead of controlled namespace labels for policy**
- **Assuming internal traffic is safe because it is "inside the cluster"**

---

## Phase 4: Workload and Container Security

### 4.1 Pod Security Standards Are the Native Baseline

Kubernetes replaced PodSecurityPolicy with Pod Security Standards plus Pod Security Admission. You need to understand all three policy levels:

- **Privileged**
  - Mostly unrestricted. Useful only for special trusted system workloads.
- **Baseline**
  - Prevents many obviously dangerous settings while staying compatible with a broad set of applications.
- **Restricted**
  - The strongest mainstream baseline and the best default target for ordinary apps; docs: [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/), [Pod Security Admission](https://kubernetes.io/docs/concepts/security/pod-security-admission/).

### 4.2 Pod Security Admission: How Enforcement Actually Happens

- **Namespace labels drive enforcement**
  - Learn the `enforce`, `warn`, and `audit` modes and how teams phase them in safely; docs: [Pod Security Admission](https://kubernetes.io/docs/concepts/security/pod-security-admission/).
- **Production rollout pattern**
  - Start with `warn` and `audit`
  - fix manifests
  - then move critical namespaces to `enforce`
- **Do not leave sensitive namespaces permanently in soft-only mode**
  - That defeats the point of the control.

### 4.3 `securityContext` Is One of the Highest Leverage Manifest Skills

You should be comfortable reading and setting:

- `runAsNonRoot`
- `runAsUser`
- `runAsGroup`
- `fsGroup`
- `allowPrivilegeEscalation: false`
- `readOnlyRootFilesystem: true`
- `capabilities.drop`
- `seccompProfile`

Study docs: [Configure a Security Context for a Pod or Container](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/).

### 4.4 Linux Kernel Hardening Features Matter

- **seccomp**
  - Filters allowed syscalls to reduce kernel attack surface.
- **AppArmor**
  - Policy-based mandatory access control for file and capability behaviors on supported hosts.
- **SELinux**
  - Strong label-based mandatory access control, especially important in environments already standardized on SELinux.
- **Why this matters**
  - Upstream explicitly notes that privileged containers override or ignore many of these protections; docs: [Linux kernel security constraints for Pods and containers](https://kubernetes.io/docs/concepts/security/linux-kernel-security-constraints/).

### 4.5 Privileged Containers Are a Serious Exception Case

- **`privileged: true` should be rare**
  - It effectively blows through many other hardening controls.
- **Capabilities are usually better than full privilege**
  - Grant only what is actually required.
- **Keep privileged workloads isolated**
  - Dedicated nodes, taints, and tighter RBAC/service account handling reduce blast radius; docs: [Linux kernel security constraints for Pods and containers](https://kubernetes.io/docs/concepts/security/linux-kernel-security-constraints/), [RBAC Good Practices](https://kubernetes.io/docs/concepts/security/rbac-good-practices/).

### 4.6 Image Security and Supply Chain Security Are Part of Kubernetes Security

- **Use minimal, maintained base images**
- **Pin versions intentionally**
- **Scan images continuously**
- **Know where images are allowed to come from**
- **Prefer signed and verifiable artifacts where possible**
- **Treat CI/CD as part of cluster security**
  - If your pipeline can push bad manifests or poisoned images, your cluster is only as safe as that pipeline.

Upstream docs that help frame this area:

- [Application Security Checklist](https://kubernetes.io/docs/concepts/security/application-security-checklist/)
- [Images](https://kubernetes.io/docs/concepts/containers/images/)

### 4.7 Node and Runtime Security Still Matter

- **Kubernetes is not a VM boundary**
  - A container breakout lands you on the node, not in some abstract layer.
- **Harden the node OS**
  - Patch aggressively, minimize packages, lock down SSH, protect kubelet, and understand runtime configuration.
- **Protect the kubelet and node credentials**
  - Node-level compromise can turn into broader compromise quickly.
- **Understand bypass risk**
  - Access paths that avoid the API server also avoid normal authorization, admission, and audit controls; docs: [Kubernetes API Server Bypass Risks](https://kubernetes.io/docs/concepts/security/api-server-bypass-risks/).

### 4.8 Other High-Value Workload Security Topics

- **User namespaces**
  - Worth understanding for stronger isolation patterns in environments that support them.
- **Sandboxed runtimes**
  - Runtime isolation technologies such as gVisor or Kata can matter for stronger tenant separation.
- **HostPath, hostNetwork, hostPID, hostIPC**
  - These are all high-risk settings that deserve scrutiny in policy and review.
- **Ephemeral containers for debugging**
  - Powerful and useful, but easy to misuse if your operational model is sloppy.

---

## Phase 5: Secrets and Sensitive Data Protection

### 5.1 Kubernetes Secrets Are Not Magic Encryption

- **A Secret object is an API object**
  - It is not inherently secure just because the kind is named `Secret`.
- **Base64 is not encryption**
  - Upstream explicitly warns about this; docs: [Good practices for Kubernetes Secrets](https://kubernetes.io/docs/concepts/security/secrets-good-practices/).
- **Anyone who can read the Secret gets the secret**
  - That sounds obvious, but many clusters effectively grant this too widely via RBAC, controller permissions, or namespace over-sharing.

### 5.2 Native Secret Good Practices

- **Restrict who can read or create Secrets**
  - This is one of the most important RBAC boundaries in the cluster.
- **Avoid putting long-lived credentials in manifests**
  - Never confuse YAML convenience with acceptable security.
- **Mount only where needed**
  - If only one container in a Pod needs a secret, mount it only there.
- **Protect data after the app reads it**
  - Avoid cleartext logging, debugging dumps, and accidental retransmission; docs: [Good practices for Kubernetes Secrets](https://kubernetes.io/docs/concepts/security/secrets-good-practices/), [Secrets](https://kubernetes.io/docs/concepts/configuration/secret/).

### 5.3 Encrypt Secret Data at Rest

- **Do this in production**
  - Enable encryption at rest for Secrets in etcd. Otherwise a backup, disk snapshot, or etcd access path may expose raw secret values; docs: [Encrypting Confidential Data at Rest](https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/).
- **Know what is encrypted**
  - Study which resources are covered and how key rotation works.
- **Know where your KMS keys live**
  - In managed platforms, this often ties into cloud KMS services and provider-managed control planes.

### 5.4 Secrets in Git: The Sealed Secrets Question

This is a very common real-world topic.

- **Sealed Secrets**
  - Encrypts a secret into a git-storable SealedSecret resource that can only be decrypted by the controller in the target cluster; docs: [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets).
- **Why teams like it**
  - Simple GitOps story
  - easy developer workflow
  - no plain secret values in Git
- **What to think about**
  - Key management
  - rotation strategy
  - cluster coupling
  - disaster recovery if keys are lost

### 5.5 Important Alternatives to Sealed Secrets

- **External Secrets Operator**
  - Syncs secrets from external backends like AWS Secrets Manager, GCP Secret Manager, Azure Key Vault, Vault, and others into Kubernetes; docs: [External Secrets Operator](https://external-secrets.io/latest/).
- **Secrets Store CSI Driver**
  - Mounts secrets from external secret stores into Pods, often avoiding persistence as standard Kubernetes Secret objects depending on your design; docs: [Secrets Store CSI Driver](https://secrets-store-csi-driver.sigs.k8s.io/).
- **Cloud-provider native secret stores**
  - Often the most natural option if you are already standardized on a cloud KMS and secret manager ecosystem.

### 5.6 How to Think About the Tradeoffs

Use this mental model:

- **Use native Kubernetes Secrets**
  - For simple clusters, low-risk config, or when external secret dependencies would be overkill.
- **Use Sealed Secrets**
  - When GitOps-first workflows matter and you want encrypted values committed to Git.
- **Use External Secrets Operator**
  - When the source of truth should stay in an external secret manager and Kubernetes should consume, not own, the secret lifecycle.
- **Use Secrets Store CSI Driver**
  - When runtime-mounted secret material is preferable to syncing secret values into the API.

### 5.7 Other Sensitive Data Concerns People Forget

- **Backups**
  - etcd backups and volume snapshots may contain secret data.
- **CI logs**
  - Secret leakage often happens in pipelines, not just in Pods.
- **Crash dumps and debug output**
  - Memory and stack traces can become a secret exposure path.
- **Developer tooling**
  - Local `.env` files, shell history, and copied kubeconfigs routinely become the weakest link.

---

## Phase 6: Audit, Detection, and Response

### 6.1 Audit Logging Is Core Production Hygiene

- **What it is**
  - The API server emits audit events for requests as they move through execution stages, based on an audit policy; docs: [Auditing](https://kubernetes.io/docs/tasks/debug/debug-cluster/audit/).
- **What to learn**
  - Audit stages
  - policy rules
  - log backend vs webhook backend
  - retention and downstream SIEM ingestion
- **Why it matters**
  - If you cannot answer "who changed this RoleBinding" or "who created this privileged Pod," your incident response is already in trouble.

### 6.2 Good Audit Questions

- Who created or modified cluster-admin-like bindings?
- Who accessed or listed Secrets?
- Who created privileged Pods or workloads with host access?
- Who changed admission or policy resources?
- Which service accounts are making unexpected API calls?

### 6.3 Logging Beyond Audit

- **Control plane logs**
  - Required for operational investigation.
- **Node and kubelet logs**
  - Important when runtime compromise or bypass risk is involved.
- **Application logs**
  - Must not accidentally print credentials or tokens.
- **Security event logs**
  - Runtime detections, policy violations, admission denials, and image scan failures should flow somewhere centralized.

### 6.4 Runtime Detection Is the Missing Layer in Many Clusters

- **Preventive controls are not enough**
  - You also want to know when a Pod suddenly starts spawning shells, touching sensitive paths, or making suspicious syscalls.
- **This is where runtime tooling matters**
  - Falco and similar tools are common here; docs: [Falco Documentation](https://falco.org/docs/).

### 6.5 Policy and Drift Detection

- **Policy violations should be visible**
  - It is not enough to say "we use RBAC" or "we have Pod Security Admission." You want evidence when manifests drift or exceptions pile up.
- **Continuously scan**
  - Images, manifests, clusters, and IaC all need scanning, not just one of them.

### 6.6 Incident Response Topics to Study

- Credential revocation and rotation
- Break-glass access design
- What to do after a node compromise
- How to evict or quarantine suspicious workloads
- How to preserve logs and audit trails
- How to re-establish trust in image supply and CI pipelines

---

## Phase 7: Important Third-Party Security Topics

Kubernetes gives you the primitives, not a complete production security platform. These ecosystem tools matter because they solve real gaps teams hit quickly.

### 7.1 Secrets, Certificates, and Identity Ecosystem

| Topic | Why it matters | Docs |
|---|---|---|
| `Sealed Secrets` | Encrypt secrets for GitOps workflows | [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets) |
| `External Secrets Operator` | Sync secret values from external secret managers | [External Secrets Operator](https://external-secrets.io/latest/) |
| `Secrets Store CSI Driver` | Mount secrets from external backends into Pods | [Secrets Store CSI Driver](https://secrets-store-csi-driver.sigs.k8s.io/) |
| `cert-manager` | Automate certificate issuance and rotation inside clusters | [cert-manager docs](https://cert-manager.io/docs/) |

### 7.2 Policy as Code

| Topic | Why it matters | Docs |
|---|---|---|
| `Kyverno` | Kubernetes-native policy engine for validation, mutation, and generation | [Kyverno docs](https://kyverno.io/docs/) |
| `OPA Gatekeeper` | OPA/Rego-based admission policy and audit tooling | [Gatekeeper docs](https://open-policy-agent.github.io/gatekeeper/website/docs/) |

These tools matter because native Pod Security Admission is intentionally narrow. Real teams often need policy around image registries, label conventions, hostPath usage, resource requests, signing requirements, or exception management.

### 7.3 Runtime and Detection Tooling

| Topic | Why it matters | Docs |
|---|---|---|
| `Falco` | Runtime detection for suspicious container and node activity | [Falco docs](https://falco.org/docs/) |
| `Trivy` | Scan images, filesystem content, Kubernetes manifests, and IaC for vulnerabilities/misconfigurations | [Trivy docs](https://trivy.dev/latest/docs/) |

### 7.4 Software Supply Chain and Signature Verification

| Topic | Why it matters | Docs |
|---|---|---|
| `Sigstore Policy Controller` | Enforce image signature and attestation policies in-cluster | [Sigstore Policy Controller docs](https://docs.sigstore.dev/policy-controller/overview/) |

This area is important because "trusted registry" is not the same thing as "trusted artifact." Mature teams move toward signed images, provenance, and admission-time verification.

### 7.5 How to Prioritize Third-Party Topics

If you are learning for practical production work, this is a strong order:

1. `cert-manager`
2. `External Secrets Operator` or `Secrets Store CSI Driver`
3. `Kyverno` or `Gatekeeper`
4. `Falco`
5. `Trivy`
6. `Sealed Secrets`
7. `Sigstore Policy Controller`

That order is not universal, but it maps well to the controls most teams need first.

---

## Phase 8: Production Hardening Checklist

### 8.1 Identity and Access

- Use OIDC or managed-cluster identity integration for human users.
- Require MFA through the upstream IdP where possible.
- Avoid shared admin accounts and avoid `system:masters`.
- Use groups, not one-off user bindings.
- Prefer namespace-scoped roles over cluster-wide access.
- Review all permissions that allow reading Secrets, creating Pods, issuing certificates, impersonating identities, or binding/escalating roles.
- Use dedicated ServiceAccounts for workloads.
- Disable service account token automount where workloads do not need API access.
- Prefer projected short-lived tokens and workload identity federation to static cloud credentials.

### 8.2 Workload Hardening

- Enforce Pod Security Admission for app namespaces.
- Run as non-root by default.
- Set `allowPrivilegeEscalation: false`.
- Drop Linux capabilities by default and add only what is required.
- Use a read-only root filesystem where practical.
- Use seccomp profiles and stronger kernel MAC features where your platform supports them.
- Treat `privileged`, `hostNetwork`, `hostPID`, `hostIPC`, and `hostPath` as exception-only settings.

### 8.3 Network and Tenancy

- Implement default-deny ingress and egress policies.
- Explicitly allow DNS and required service dependencies.
- Segment public, internal, and admin traffic paths.
- Be cautious about multi-tenancy assumptions.
- Use dedicated nodes or stronger isolation for sensitive workloads when required.

### 8.4 Secrets and Data

- Enable encryption at rest for Secrets in etcd.
- Keep secret sources of truth outside Git unless using an intentional encrypted workflow.
- Limit who can read, create, and update Secrets.
- Avoid static cloud access keys in Secret objects if federation is available.
- Protect backups, snapshots, and exported manifests.

### 8.5 Audit and Monitoring

- Enable audit logging with a reviewed policy.
- Forward audit logs and control plane logs to a durable system.
- Monitor for suspicious RBAC, Secret, and privileged workload events.
- Continuously scan images and manifests.
- Regularly review policy violations and cluster exceptions.

### 8.6 Platform and Operations

- Patch Kubernetes, node OS, and runtimes consistently.
- Keep admission, CNI, and ingress components updated.
- Protect the kubelet and node credentials.
- Design break-glass access before an incident, not during one.
- Test restore and secret recovery workflows.

---

## Hands-On Labs

### Lab 1: OIDC and RBAC Design Exercise

- Draw the identity path for human access into a cluster using OIDC.
- Map groups from an IdP to namespace-scoped RBAC roles.
- Identify which users truly need cluster-wide visibility.
- Create a break-glass cluster-admin path and describe how it would be audited.

### Lab 2: Service Account Hardening

- Create two workloads in a namespace:
  - one that needs no Kubernetes API access
  - one that needs read-only access to ConfigMaps
- Disable automount for the first.
- Create a dedicated ServiceAccount and least-privilege Role/RoleBinding for the second.
- Explain why the default ServiceAccount is not a good long-term answer.

### Lab 3: NetworkPolicy Default-Deny Rollout

- Apply default-deny ingress and egress in a test namespace.
- Add rules for DNS.
- Add rules for app-to-database traffic.
- Verify that unrelated Pods can no longer connect.
- Confirm your CNI is actually enforcing policy.

### Lab 4: Pod Security Admission Rollout

- Label a namespace with `warn` and `audit` for the Restricted standard.
- Deploy a workload that violates Restricted.
- Fix the manifest by setting:
  - `runAsNonRoot`
  - `allowPrivilegeEscalation: false`
  - capability drops
  - a seccomp profile
- Move the namespace to `enforce`.

### Lab 5: Secret Management Comparison

Pick one secret, such as a database password, and compare four ways of handling it:

1. Native Kubernetes Secret
2. Sealed Secrets
3. External Secrets Operator
4. Secrets Store CSI Driver

For each, answer:

- Where is the source of truth?
- Does the secret live in Git?
- Does it persist in the Kubernetes API?
- How is rotation handled?
- What happens during disaster recovery?

### Lab 6: Audit Logging

- Enable or inspect audit logging on a cluster.
- Create a low-risk audit policy focused on:
  - Secret access
  - RBAC changes
  - privileged workload creation
- Generate sample events and confirm they are captured.

### Lab 7: Supply Chain Security

- Scan a container image with Trivy.
- Identify high/critical vulnerabilities.
- Decide whether to block deployment or document a compensating control.
- If your environment supports it, design an admission policy that only allows approved registries or signed images.

---

## What Good Looks Like in Production

A healthy production Kubernetes security posture usually looks like this:

- Human users authenticate through OIDC or the managed-cluster identity integration, not shared static credentials.
- RBAC is group-based, least-privilege, and periodically reviewed.
- App namespaces are under Pod Security Admission enforcement.
- ServiceAccounts are specific to workloads, and most Pods do not get unnecessary API credentials.
- NetworkPolicy default-deny is normal, not exotic.
- Secrets are encrypted at rest and ideally sourced from an external secret manager or an intentional GitOps encryption workflow.
- Audit logs exist, are retained, and are actually reviewed.
- Image scanning and policy enforcement are part of CI/CD, not an afterthought.
- Privileged workloads are rare and isolated.
- The platform team understands how to rotate credentials, investigate suspicious activity, and recover trust after an incident.

If you remember only one thing from this guide, remember this: the dangerous Kubernetes failures are usually not "a missing feature." They are combinations of small permissions, weak defaults, and invisible operational shortcuts that line up into a full compromise path.

---

## Recommended Study Order

If you want the fastest path to practical competence, study in this order:

1. Authentication models, ServiceAccounts, and RBAC
2. Pod Security Standards, `securityContext`, and privileged-container risks
3. NetworkPolicy and multi-tenancy basics
4. Secrets handling and encryption at rest
5. Audit logging and incident investigation
6. Managed-cluster IAM integrations
7. Third-party policy, runtime, and supply-chain tooling

---

## Primary Documentation Index

### Upstream Kubernetes

- [Controlling Access to the Kubernetes API](https://kubernetes.io/docs/concepts/security/controlling-access/)
- [Authenticating](https://kubernetes.io/docs/reference/access-authn-authz/authentication/)
- [Using RBAC Authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- [Admission Controllers](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/)
- [Validating Admission Policy](https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/)
- [Role Based Access Control Good Practices](https://kubernetes.io/docs/concepts/security/rbac-good-practices/)
- [Hardening Guide - Authentication Mechanisms](https://kubernetes.io/docs/concepts/security/hardening-guide/authentication-mechanisms/)
- [PKI certificates and requirements](https://kubernetes.io/docs/setup/best-practices/certificates/)
- [Issue a Certificate for a Kubernetes API Client Using A CertificateSigningRequest](https://kubernetes.io/docs/tasks/tls/certificate-issue-client-csr/)
- [Service Accounts](https://kubernetes.io/docs/concepts/security/service-accounts/)
- [Configure Service Accounts for Pods](https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/)
- [Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [Pod Security Admission](https://kubernetes.io/docs/concepts/security/pod-security-admission/)
- [Linux kernel security constraints for Pods and containers](https://kubernetes.io/docs/concepts/security/linux-kernel-security-constraints/)
- [Configure a Security Context for a Pod or Container](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/)
- [Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Good practices for Kubernetes Secrets](https://kubernetes.io/docs/concepts/security/secrets-good-practices/)
- [Encrypting Confidential Data at Rest](https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/)
- [Auditing](https://kubernetes.io/docs/tasks/debug/debug-cluster/audit/)
- [Security Checklist](https://kubernetes.io/docs/concepts/security/security-checklist/)
- [Application Security Checklist](https://kubernetes.io/docs/concepts/security/application-security-checklist/)
- [Multi-tenancy](https://kubernetes.io/docs/concepts/security/multi-tenancy/)
- [Kubernetes API Server Bypass Risks](https://kubernetes.io/docs/concepts/security/api-server-bypass-risks/)

### Managed Kubernetes Identity Docs

- [EKS access entries](https://docs.aws.amazon.com/eks/latest/userguide/setting-up-access-entries.html)
- [EKS IAM roles for service accounts](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html)
- [GKE external identity providers / OIDC](https://cloud.google.com/kubernetes-engine/docs/how-to/oidc)
- [GKE Workload Identity Federation](https://cloud.google.com/kubernetes-engine/docs/concepts/workload-identity)
- [AKS Microsoft Entra integration](https://learn.microsoft.com/en-us/azure/aks/enable-authentication-microsoft-entra-id)
- [AKS Microsoft Entra Workload ID](https://learn.microsoft.com/en-us/azure/aks/workload-identity-overview)
- [AKS OIDC issuer](https://learn.microsoft.com/en-us/azure/aks/use-oidc-issuer)

### Important Ecosystem Security Docs

- [Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets)
- [External Secrets Operator](https://external-secrets.io/latest/)
- [Secrets Store CSI Driver](https://secrets-store-csi-driver.sigs.k8s.io/)
- [cert-manager](https://cert-manager.io/docs/)
- [Kyverno](https://kyverno.io/docs/)
- [OPA Gatekeeper](https://open-policy-agent.github.io/gatekeeper/website/docs/)
- [Falco](https://falco.org/docs/)
- [Trivy](https://trivy.dev/latest/docs/)
- [Sigstore Policy Controller](https://docs.sigstore.dev/policy-controller/overview/)
