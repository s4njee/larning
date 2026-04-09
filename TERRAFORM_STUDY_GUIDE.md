# Terraform Mastery Study Guide

A comprehensive, job-focused guide to mastering Terraform for real infrastructure teams. Learn the CLI, the language, the state model, and the operational discipline that makes Terraform safe at scale. Build reusable infrastructure, not one-off demo configs.

As of April 9, 2026, HashiCorp's official docs list Terraform v1.14.x as the latest stable line and v1.15.x as beta. This guide assumes v1.14-era workflows; if you are working in an older repo or a managed platform with pinned versions, verify version-specific features before relying on them.

---

## Phase 1: Core Foundations

### 1.1 What Terraform Actually Does

- **Declarative infrastructure as code**: You describe the desired end state, not the imperative steps to get there
  - The biggest mindset shift is moving from "run these commands" to "declare these objects and relationships," because Terraform is built around convergence and diffing, not shell scripting; docs: [Terraform Language](https://developer.hashicorp.com/terraform/language), [Terraform Workflow](https://developer.hashicorp.com/terraform/cli/run).
- **Terraform CLI**: Reads configuration, builds a dependency graph, asks providers for a diff, and then executes the plan
  - When a run behaves strangely, it helps to separate which layer owns the problem: your HCL, the Terraform CLI, the provider plugin, the backend, or the cloud API; docs: [Terraform CLI](https://developer.hashicorp.com/terraform/cli), [Terraform Workflow](https://developer.hashicorp.com/terraform/cli/run).
- **Providers**: Plugins that translate Terraform resource declarations into real API calls
  - Terraform itself does not know how to create a VPC, a VM, or a DNS record; providers do, which is why provider selection, versioning, and docs matter so much; docs: [Provider Requirements](https://developer.hashicorp.com/terraform/language/providers/requirements), [Provider Configuration](https://developer.hashicorp.com/terraform/language/providers/configuration).
- **State**: Terraform's record of which real-world object corresponds to which resource address in your configuration
  - State is not just an output artifact; it is the mapping layer Terraform needs in order to update, replace, or destroy the correct object later; docs: [State](https://developer.hashicorp.com/terraform/language/state).
- **Plan and apply**: `terraform plan` previews a proposed change set, `terraform apply` executes it
  - Professional Terraform work means reviewing plans carefully before execution, especially for destructive changes, replacements, and unexpected drift; docs: [terraform plan](https://developer.hashicorp.com/terraform/cli/commands/plan), [terraform apply](https://developer.hashicorp.com/terraform/cli/commands/apply).
- **Dependency graph**: Terraform infers order from references and only needs explicit `depends_on` in edge cases
  - Strong Terraform code models dependencies through data flow first, because explicit ordering hacks usually signal weak resource boundaries or missing outputs; docs: [Expressions](https://developer.hashicorp.com/terraform/language/expressions), [Meta-arguments](https://developer.hashicorp.com/terraform/language/meta-arguments).
- **Convergence over repeated runs**: Re-running the same configuration should produce no changes unless the real infrastructure or inputs changed
  - That is why manual changes, provider defaults, and unstable naming patterns show up so painfully in Terraform: they break predictability; docs: [Terraform Workflow](https://developer.hashicorp.com/terraform/cli/run), [State](https://developer.hashicorp.com/terraform/language/state).

### 1.2 Project Setup and File Structure

- **`terraform` block**: Declare `required_version`, `required_providers`, and either a `backend` or `cloud` integration
  - Pinning versions early is one of the cheapest ways to avoid "works on my machine" provider drift across developers and CI; docs: [terraform block reference](https://developer.hashicorp.com/terraform/language/block/terraform), [Provider Requirements](https://developer.hashicorp.com/terraform/language/providers/requirements).
- **Style-guide file layout**: Start with a conventional structure before you invent your own conventions
  - Consistent file names make Terraform repos much easier to review and maintain, especially once multiple people are touching the same root module; docs: [Style Guide](https://developer.hashicorp.com/terraform/language/style).
  ```hcl
  .
  |-- terraform.tf   # required_version, required_providers
  |-- providers.tf   # provider configuration
  |-- backend.tf     # backend or cloud configuration
  |-- variables.tf   # input variables
  |-- locals.tf      # derived naming, tags, repeated expressions
  |-- main.tf        # core resources
  |-- outputs.tf     # outputs
  `-- modules/
      |-- network/
      `-- app/
  ```
- **Code organization by domain**: Split large configurations into `network.tf`, `compute.tf`, `storage.tf`, etc. once `main.tf` becomes noisy
  - File splitting should improve discoverability, not scatter a small configuration across a dozen files for no reason; docs: [Style Guide](https://developer.hashicorp.com/terraform/language/style).
- **`terraform fmt`**: Format your configuration consistently
  - Run this constantly so review time stays focused on behavior, blast radius, and provider semantics instead of formatting churn; docs: [terraform fmt](https://developer.hashicorp.com/terraform/cli/commands/fmt).
- **`terraform validate`**: Catch syntax errors and internal inconsistencies before planning
  - Validation is safe to automate and should become part of your editor, pre-commit hooks, and CI from day one; docs: [terraform validate](https://developer.hashicorp.com/terraform/cli/commands/validate).
- **`.terraform.lock.hcl`**: Dependency lock file for providers
  - Commit the lock file so your team and remote runners install the same provider versions and checksums by default; docs: [Dependency Lock File](https://developer.hashicorp.com/terraform/language/files/dependency-lock), [Provider Requirements](https://developer.hashicorp.com/terraform/language/providers/requirements).
- **Registry-first workflow**: Use the Terraform Registry as your canonical source for provider and module docs
  - Most day-to-day Terraform work is really "provider docs literacy," because resources and arguments come from providers much more than from Terraform core; docs: [Terraform Registry](https://registry.terraform.io/).

### 1.3 Core CLI Workflow

- **`terraform init`**: Initialize the working directory, install providers and modules, and configure the backend
  - Any time you change provider requirements, backend settings, or module sources, `init` is the first command to re-run; docs: [terraform init](https://developer.hashicorp.com/terraform/cli/commands/init).
- **`terraform plan`**: Compute the proposed diff without making changes
  - Treat plan review like code review for infrastructure, because this is where you catch unintended replacements, deletes, and drift before they become incidents; docs: [terraform plan](https://developer.hashicorp.com/terraform/cli/commands/plan).
- **Saved plans**: Use `terraform plan -out=...` when you need approval and execution to share the exact same artifact
  - This matters in team workflows because "reviewed plan" and "applied plan" should be the same thing, not two separate computations against a moving target; docs: [terraform plan](https://developer.hashicorp.com/terraform/cli/commands/plan), [terraform apply](https://developer.hashicorp.com/terraform/cli/commands/apply).
- **`terraform apply`**: Execute a plan after review
  - Teams that move safely with Terraform are not necessarily slow; they are disciplined about review boundaries and approvals; docs: [terraform apply](https://developer.hashicorp.com/terraform/cli/commands/apply).
- **`terraform show`**: Render plan files and state in human-readable or JSON form
  - `show -json` becomes useful once you start integrating policy engines, CI gates, or custom plan analysis; docs: [terraform show](https://developer.hashicorp.com/terraform/cli/commands/show).
- **`terraform output`**: Read outputs from state cleanly
  - Outputs are how a root module exposes useful values to operators and downstream systems without forcing them to inspect raw state; docs: [terraform output](https://developer.hashicorp.com/terraform/cli/commands/output), [Outputs](https://developer.hashicorp.com/terraform/language/values/outputs).
- **`terraform destroy`**: Tear down managed infrastructure
  - You should practice destruction workflows early, because safe cleanup, temporary environments, and cost control are all part of real-world Terraform use; docs: [Terraform Workflow](https://developer.hashicorp.com/terraform/cli/run).

### 1.4 HCL and the Configuration Model

- **Blocks and arguments**: Terraform configurations are mostly nested blocks with named arguments
  - Once you internalize that resources, providers, variables, outputs, and modules are all just structured blocks, Terraform becomes much easier to read; docs: [Terraform Language](https://developer.hashicorp.com/terraform/language).
- **Expressions**: Values can be literals, references, conditionals, comprehensions, or function calls
  - Strong Terraform authors spend a lot of time in expressions because that is where repetition becomes reusable logic instead of copy-paste; docs: [Expressions](https://developer.hashicorp.com/terraform/language/expressions), [Functions](https://developer.hashicorp.com/terraform/language/functions).
- **References**: `var`, `local`, `data`, `module`, and resource addresses are the vocabulary of Terraform data flow
  - If you can trace where a value comes from and who consumes it, you can usually debug the configuration; docs: [Expressions](https://developer.hashicorp.com/terraform/language/expressions).
- **Known vs unknown values**: Some attributes are only known after apply
  - A lot of confusing plan output becomes clearer once you understand that Terraform often plans around placeholders for values that do not exist yet; docs: [Expressions](https://developer.hashicorp.com/terraform/language/expressions).
- **Comments and readability**: Use `#` comments sparingly and write code that mostly explains itself
  - Terraform is usually easiest to maintain when naming, file structure, and module boundaries do most of the explanatory work; docs: [Style Guide](https://developer.hashicorp.com/terraform/language/style).

**Practice**: Create a small root module with a pinned Terraform version, pinned provider version, variables, locals, outputs, and at least two resources. Run `terraform init`, `terraform fmt`, `terraform validate`, `terraform plan -out=tfplan`, and `terraform show tfplan`.

---

## Phase 2: Modeling Infrastructure with Terraform Language Features

### 2.1 Providers, Resources, and Data Sources

- **Provider requirements**: Declare provider source addresses and version constraints in `required_providers`
  - This is the contract that tells Terraform what plugins your configuration depends on and which versions are considered compatible; docs: [Provider Requirements](https://developer.hashicorp.com/terraform/language/providers/requirements).
- **Provider configuration**: Configure region, credentials strategy, aliases, and provider-specific arguments in `provider` blocks
  - Keep provider config centralized and explicit so multi-region or multi-account behavior is not hidden inside child modules; docs: [Provider Configuration](https://developer.hashicorp.com/terraform/language/providers/configuration).
- **Resources**: `resource` blocks manage actual infrastructure objects
  - Resource blocks are the heart of Terraform, so learn to read provider docs carefully for required attributes, computed fields, and replace-vs-update behavior; docs: [resource block reference](https://developer.hashicorp.com/terraform/language/block/resource).
- **Data sources**: `data` blocks read existing information without managing lifecycle
  - Data sources are powerful, but overusing them can create fragile plans if you depend on too much ambient infrastructure state; docs: [Data Sources](https://developer.hashicorp.com/terraform/language/data-sources).
- **Provider aliases**: Use aliased providers for multiple regions, accounts, or clusters
  - This is the clean way to model multi-target infrastructure without duplicating root modules unnecessarily; docs: [Provider Configuration](https://developer.hashicorp.com/terraform/language/providers/configuration).
- **Registry docs literacy**: Most arguments, defaults, and lifecycle quirks live in provider docs, not in Terraform core docs
  - You should get comfortable jumping between Terraform core references and provider registry pages constantly; docs: [Terraform Registry](https://registry.terraform.io/).

### 2.2 Variables, Locals, and Outputs

- **Input variables**: Define configurable module inputs with `type`, `description`, and optional defaults
  - Treat variables as your module's public API, because unclear or weakly typed inputs make reuse painful fast; docs: [Variables](https://developer.hashicorp.com/terraform/language/values/variables).
- **Type constraints**: Use precise types like `object`, `map(string)`, or `list(object({...}))`
  - Strong typing catches mistakes earlier and makes module expectations obvious to consumers; docs: [Variables](https://developer.hashicorp.com/terraform/language/values/variables).
- **Variable validation**: Add `validation` rules to reject bad inputs before planning goes too far
  - Validation is one of the easiest ways to turn module assumptions into enforceable contracts; docs: [Validate your configuration](https://developer.hashicorp.com/terraform/language/validate), [Variables](https://developer.hashicorp.com/terraform/language/values/variables).
- **Locals**: Use `locals` for repeated expressions, standardized names, tags, and derived values
  - Good locals reduce duplication; bad locals hide simple values behind unnecessary indirection, so keep them purposeful; docs: [Locals](https://developer.hashicorp.com/terraform/language/values/locals).
- **Outputs**: Expose only the values that consumers or operators truly need
  - Outputs are your module boundary, so keep them deliberate and documented instead of dumping every attribute "just in case"; docs: [Outputs](https://developer.hashicorp.com/terraform/language/values/outputs).
- **Sensitive values**: `sensitive = true` redacts output but does not keep the value out of state
  - This is a classic Terraform gotcha: redacted output is not the same as secret-safe storage; docs: [Manage sensitive data](https://developer.hashicorp.com/terraform/language/manage-sensitive-data), [Variables](https://developer.hashicorp.com/terraform/language/values/variables).
- **Value precedence**: Learn the order of `-var`, `-var-file`, `*.auto.tfvars`, `terraform.tfvars`, environment variables, and defaults
  - This matters when a plan is using the "wrong" value and nobody remembers where it came from; docs: [Variables](https://developer.hashicorp.com/terraform/language/values/variables).

### 2.3 Expressions and Functions

- **Conditionals**: `condition ? true_val : false_val`
  - Use conditionals for small decisions, not for building giant multi-environment branching trees inside one root module; docs: [Conditional Expressions](https://developer.hashicorp.com/terraform/language/expressions/conditionals).
- **`for` expressions**: Build new collections from old ones
  - `for` expressions are one of the key tools for transforming human-friendly inputs into provider-friendly structures; docs: [For Expressions](https://developer.hashicorp.com/terraform/language/expressions/for).
- **String templates and heredocs**: Build user data, policies, configuration files, and naming patterns
  - Prefer `templatefile()` once string construction starts getting large or multi-line; docs: [Expressions](https://developer.hashicorp.com/terraform/language/expressions), [Functions](https://developer.hashicorp.com/terraform/language/functions).
- **`terraform console`**: Interactive REPL for testing expressions and functions
  - This is one of the fastest ways to debug maps, lists, conditionals, and subnet math without doing a full apply; docs: [terraform console](https://developer.hashicorp.com/terraform/cli/commands/console).
- **Collection and utility functions**: Learn the small set you will use constantly
  - Terraform fluency often looks like knowing when to reach for the right built-in function rather than writing awkward nested expressions; docs: [Functions](https://developer.hashicorp.com/terraform/language/functions).

| Function | Why it matters |
|---|---|
| `merge()` | Combine standard tag maps, labels, or repeated object settings |
| `lookup()` | Safely read optional map keys with defaults |
| `try()` / `can()` | Defend against absent attributes and optional structures |
| `coalesce()` / `coalescelist()` | Pick the first non-null or non-empty value |
| `jsonencode()` / `yamlencode()` | Render valid machine-readable configuration without manual escaping |
| `templatefile()` | Keep complex templates outside inline strings |
| `flatten()` / `distinct()` / `toset()` | Normalize collections before `for_each` |
| `cidrsubnet()` / `cidrhost()` | Essential network math for VPCs, subnets, and host addressing |

### 2.4 Meta-arguments and Repetition

- **`for_each`**: Preferred for stable, keyed repetition over maps or sets
  - Keyed instances are easier to reason about and refactor than numeric indexes when infrastructure grows or items are reordered; docs: [for_each](https://developer.hashicorp.com/terraform/language/meta-arguments/for_each).
- **`count`**: Useful for simple conditional creation or uniform replication
  - `count` is fine for truly index-like resources, but it becomes painful when instances need stable identity; docs: [Meta-arguments](https://developer.hashicorp.com/terraform/language/meta-arguments).
- **`depends_on`**: Explicit dependency escape hatch
  - Use this only when the dependency is real but not visible through data flow, because overusing it makes plans harder to understand and maintain; docs: [Meta-arguments](https://developer.hashicorp.com/terraform/language/meta-arguments).
- **`lifecycle`**: Control replacement behavior with tools like `create_before_destroy`, `prevent_destroy`, `ignore_changes`, and `replace_triggered_by`
  - Lifecycle settings can save you from downtime or surprises, but they can also hide drift or block necessary changes if used carelessly; docs: [lifecycle](https://developer.hashicorp.com/terraform/language/meta-arguments/lifecycle).
- **Dynamic blocks**: Generate nested blocks programmatically
  - Dynamic blocks are powerful for repetitive nested provider structures, but if you reach for them too often, it may signal that your input model is too complex; docs: [Dynamic Blocks](https://developer.hashicorp.com/terraform/language/expressions/dynamic-blocks).
- **Meta-argument ordering**: Put meta-arguments first and lifecycle/meta blocks last for readability
  - Matching the style guide makes large resource blocks much easier to scan during reviews; docs: [Style Guide](https://developer.hashicorp.com/terraform/language/style).

**Practice**: Build a small network layer from a map input. Use typed variables, locals for standardized tags, `for_each` for repeated subnets, a data source for region metadata, and outputs for the resulting IDs.

---

## Phase 3: State, Backends, and Safe Change Management

### 3.1 State Fundamentals

- **State is required**: Terraform cannot manage infrastructure safely without a persistent mapping between config addresses and real objects
  - A lot of "Terraform mystery" disappears when you realize that state is the coordination layer between past applies and future plans; docs: [State](https://developer.hashicorp.com/terraform/language/state).
- **Default local state**: `terraform.tfstate` in the working directory
  - Local state is fine for learning, but it breaks down quickly for shared infrastructure because collaboration, locking, and secure sharing are all weak; docs: [State](https://developer.hashicorp.com/terraform/language/state).
- **Refresh and drift**: Terraform refreshes its view of managed objects before computing changes
  - Manual edits in the cloud console are not invisible; they often show up later as unexpected diffs, replacements, or policy failures; docs: [State](https://developer.hashicorp.com/terraform/language/state), [terraform plan](https://developer.hashicorp.com/terraform/cli/commands/plan).
- **Do not hand-edit state JSON**: Use Terraform commands or configuration-based refactors instead
  - State is technically JSON, but manual edits are one of the fastest ways to create irrecoverable confusion in shared infrastructure; docs: [State](https://developer.hashicorp.com/terraform/language/state), [terraform state](https://developer.hashicorp.com/terraform/cli/commands/state).
- **`terraform state` subcommands**: Inspect and repair state intentionally when needed
  - Learn these commands well enough to work calmly during migrations and imports, but do not turn them into your default refactoring tool; docs: [terraform state](https://developer.hashicorp.com/terraform/cli/commands/state).

### 3.2 Backends, Locking, and Remote State Storage

- **Backends**: Determine where state is stored and how operations coordinate
  - Backend choice is an operational concern, not just a technical detail, because it affects locking, secrets exposure, team access, and disaster recovery; docs: [terraform block reference](https://developer.hashicorp.com/terraform/language/block/terraform), [State](https://developer.hashicorp.com/terraform/language/state).
- **Remote state is the production default**: Use a shared backend or HCP Terraform for team workflows
  - Shared infrastructure managed from local state files is a reliability trap; docs: [State](https://developer.hashicorp.com/terraform/language/state), [HCP Terraform](https://developer.hashicorp.com/terraform/cloud-docs).
- **Locking**: Prevent concurrent state mutation
  - Without locking, two operators or pipelines can step on each other and corrupt the logical workflow even if the file itself survives; docs: [State](https://developer.hashicorp.com/terraform/language/state), [terraform import](https://developer.hashicorp.com/terraform/cli/commands/import).
- **Encryption and access control**: Treat state like sensitive data
  - State often contains credentials, connection details, and security-relevant metadata, so storage and access patterns matter a lot; docs: [Manage sensitive data](https://developer.hashicorp.com/terraform/language/manage-sensitive-data).
- **HCP Terraform recommendation**: HashiCorp explicitly recommends HCP Terraform for versioned, encrypted, securely shared state
  - Even if you do not use HCP for runs yet, it is worth understanding why Terraform core docs keep pointing teams there for state management; docs: [State](https://developer.hashicorp.com/terraform/language/state), [What is HCP Terraform?](https://developer.hashicorp.com/terraform/cloud-docs).

### 3.3 Workspaces and Environment Boundaries

- **CLI workspaces**: Separate state snapshots for the same root configuration
  - Terraform CLI workspaces are useful, but they are fundamentally a state-namespacing feature, not a magic answer to every environment-separation problem; docs: [terraform workspace](https://developer.hashicorp.com/terraform/cli/commands/workspace), [State](https://developer.hashicorp.com/terraform/language/state).
- **Separate directories or root modules**: Use them when environments truly diverge in topology, permissions, or lifecycle
  - If dev, staging, and prod need different providers, policies, or blast-radius boundaries, separate roots are usually clearer than deeply conditional one-size-fits-all HCL.
- **HCP workspaces**: In HCP Terraform, a workspace is the managed unit containing configuration, variables, state, and run history
  - This is different from CLI workspaces, and teams should be careful not to conflate the two ideas; docs: [HCP Terraform workspaces](https://developer.hashicorp.com/terraform/cloud-docs/workspaces).
- **Avoid environment spaghetti**: If your root module is full of `var.environment == "prod"` branches, your boundaries probably need rethinking
  - Terraform stays readable when module composition models environment differences more than conditional expressions do.

### 3.4 Imports, Moves, Removals, and Refactors

- **`import` blocks**: Bring existing infrastructure under Terraform management declaratively
  - Import is not just a recovery tool; it is a core migration skill for adopting Terraform in brownfield environments; docs: [Import resources overview](https://developer.hashicorp.com/terraform/language/import), [import block reference](https://developer.hashicorp.com/terraform/language/block/import).
- **`terraform import` CLI**: Useful when importing manually or incrementally
  - You should know both the configuration-based and CLI-based workflows, because real-world migrations are messy; docs: [terraform import](https://developer.hashicorp.com/terraform/cli/commands/import).
- **Generated config workflows**: Terraform can help generate configuration during some import flows
  - This speeds up adoption, but you still need to review the generated configuration carefully before treating it as production-ready; docs: [Import resources overview](https://developer.hashicorp.com/terraform/language/import).
- **`moved` blocks**: Refactor resource addresses without destroying infrastructure
  - This is one of the most valuable advanced Terraform skills because it lets you rename resources and extract modules while preserving state continuity; docs: [moved block reference](https://developer.hashicorp.com/terraform/language/block/moved).
- **`removed` blocks**: Stop managing a resource without destroying the underlying object
  - This is safer and more intentional than ad hoc state surgery when ownership boundaries change; docs: [removed block reference](https://developer.hashicorp.com/terraform/language/block/removed).
- **Plan every refactor**: State-aware refactors should be reviewed like schema migrations
  - Safe Terraform refactoring is less about speed and more about proving that the next plan has the exact intended blast radius.

**Practice**: Take a small root module and do three migrations safely: rename one resource with a `moved` block, stop managing another resource with a `removed` block, and import one existing external object into state.

---

## Phase 4: Modules and Reusable Architecture

### 4.1 Module Fundamentals

- **Root module vs child modules**: Every Terraform working directory is a root module, and it can call child modules
  - Think of the root module as an environment assembly layer and child modules as reusable building blocks; docs: [Modules overview](https://developer.hashicorp.com/terraform/language/modules), [module block reference](https://developer.hashicorp.com/terraform/language/block/module).
- **Module sources**: Local paths, registry modules, and VCS sources are all supported
  - Source choice affects versioning, reviewability, and reuse, so be deliberate instead of scattering modules across unversioned Git branches; docs: [Modules overview](https://developer.hashicorp.com/terraform/language/modules).
- **Module inputs and outputs**: Modules communicate through variables and outputs only
  - Good modules have explicit interfaces and do not depend on ambient global state or hidden provider magic; docs: [Variables](https://developer.hashicorp.com/terraform/language/values/variables), [Outputs](https://developer.hashicorp.com/terraform/language/values/outputs).
- **Module-level `for_each`**: Repeat entire module instances from a keyed collection
  - This is a powerful pattern for environment slices, repeated services, or region sets when the module boundary itself is the repeated unit; docs: [module block reference](https://developer.hashicorp.com/terraform/language/block/module), [for_each](https://developer.hashicorp.com/terraform/language/meta-arguments/for_each).

### 4.2 Writing Good Modules

- **Single clear purpose**: A module should model one coherent unit such as `network`, `database`, `eks_cluster`, or `dns_zone`
  - Huge kitchen-sink modules are hard to test, hard to version, and impossible to reuse cleanly; docs: [Creating Modules](https://developer.hashicorp.com/terraform/language/modules/develop).
- **Typed, documented variables**: Every public input should have a clear type and description
  - If your module consumers need tribal knowledge to use it, the interface is not ready; docs: [Variables](https://developer.hashicorp.com/terraform/language/values/variables), [Style Guide](https://developer.hashicorp.com/terraform/language/style).
- **Minimal, meaningful outputs**: Export what the next layer actually needs
  - Extra outputs create coupling and make refactors harder because downstream modules may start depending on internals accidentally; docs: [Outputs](https://developer.hashicorp.com/terraform/language/values/outputs).
- **Root owns environment-specific concerns**: Provider credentials, backend config, and workspace-specific settings usually belong in the root module
  - Reusable child modules should stay portable rather than baking in one account, one region, or one credential strategy.
- **Composition over cleverness**: Prefer small modules wired together clearly over giant expression-heavy modules
  - When Terraform gets hard to read, the fix is often simpler module boundaries rather than more HCL wizardry; docs: [Module Composition](https://developer.hashicorp.com/terraform/language/modules/develop/composition).

### 4.3 Module Versioning and Distribution

- **Version modules intentionally**: Especially registry or shared Git modules
  - Terraform teams move faster when module upgrades are planned, reviewed, and rolled out deliberately rather than consumed from floating branches.
- **Pin module versions in production roots**: Avoid implicit drift from newest-available module releases
  - Provider lock files do not lock remote module versions, so version discipline matters even more here; docs: [Dependency Lock File](https://developer.hashicorp.com/terraform/language/files/dependency-lock), [Modules overview](https://developer.hashicorp.com/terraform/language/modules).
- **Private registry workflows**: HCP Terraform includes a private registry for internal modules
  - Internal module distribution becomes dramatically more manageable once teams stop copy-pasting folder trees between repos; docs: [What is HCP Terraform?](https://developer.hashicorp.com/terraform/cloud-docs).
- **Semantic versioning mindset**: Treat module breaking changes like API breaking changes
  - A shared Terraform module is infrastructure API surface area, whether teams call it that or not.

### 4.4 Module Composition Patterns

- **Layered roots**: Environment roots call shared modules for networking, security, compute, storage, and apps
  - This is the common production shape because it balances reuse with environment ownership; docs: [Module Composition](https://developer.hashicorp.com/terraform/language/modules/develop/composition).
- **Data at the edges**: Keep data sources close to the layer that truly owns discovery
  - If every module is doing ambient lookups against the platform, debugging becomes much harder.
- **Standardized locals**: Build consistent names, tags, labels, and policy inputs once per module or root
  - Naming conventions enforced through locals are much easier to maintain than copy-pasted string patterns.
- **Provider alias injection**: Pass aliased providers into child modules explicitly for multi-region or multi-account designs
  - This makes cross-boundary behavior visible in code review instead of being hidden in assumptions; docs: [Provider Configuration](https://developer.hashicorp.com/terraform/language/providers/configuration).

**Practice**: Build two child modules, `network` and `app`, plus separate `dev` and `prod` roots that call them. Use typed variables, outputs, aliased providers where appropriate, and explicit module versioning if you split them into separate repos.

---

## Phase 5: Validation, Testing, and Quality Gates

### 5.1 Validation Inside Terraform Configuration

- **Input variable validation**: Reject bad inputs early
  - Good modules fail fast with helpful error messages instead of producing confusing provider errors halfway through planning; docs: [Validate your configuration](https://developer.hashicorp.com/terraform/language/validate), [Variables](https://developer.hashicorp.com/terraform/language/values/variables).
- **Preconditions**: Assert assumptions before resource creation or output evaluation
  - Preconditions are great for invariants that should block a plan or apply when an upstream dependency is not what you expect; docs: [Validate your configuration](https://developer.hashicorp.com/terraform/language/validate).
- **Postconditions**: Assert that created or read objects satisfy critical expectations
  - These are useful when provider defaults or external systems could produce a technically valid object that still violates your intent; docs: [Validate your configuration](https://developer.hashicorp.com/terraform/language/validate).
- **`check` blocks**: Validate broader infrastructure behavior beyond a single resource definition
  - Checks are especially useful for verifying assumptions about DNS, endpoints, connectivity, or policy compliance after provisioning; docs: [Validate your configuration](https://developer.hashicorp.com/terraform/language/validate).
- **Document intent with validation**: Validation is not just for correctness; it also teaches future maintainers what the configuration assumes
  - High-quality Terraform communicates operational expectations directly in code, not only in README files.

### 5.2 Testing with `terraform test`

- **Native testing framework**: Terraform includes a first-party testing workflow
  - This is worth learning because it lets you validate module behavior in Terraform-native terms instead of bolting on all testing logic externally; docs: [Tests](https://developer.hashicorp.com/terraform/language/tests), [terraform test](https://developer.hashicorp.com/terraform/cli/commands/test).
- **Test files drive plan/apply behavior**: Tests can run plans or applies and assert on plan/state outcomes
  - That makes module testing much closer to real infrastructure behavior than purely static linting; docs: [Tests](https://developer.hashicorp.com/terraform/language/tests), [terraform test](https://developer.hashicorp.com/terraform/cli/commands/test).
- **Real infrastructure can be created**: `terraform test` may provision real resources and incur cost
  - Terraform testing is powerful precisely because it is not fake, so cleanup, sandbox accounts, and low-cost fixtures matter; docs: [terraform test](https://developer.hashicorp.com/terraform/cli/commands/test).
- **Separate test layers**: Run `fmt` and `validate` on every commit, and reserve infra tests for modules where behavior matters
  - Not every root module needs expensive end-to-end testing, but every shared module deserves some quality gate.
- **CI-friendly outputs**: JSON and JUnit XML outputs are useful for pipelines
  - Treat Terraform tests like part of a normal engineering delivery workflow, not a special manual ritual; docs: [terraform test](https://developer.hashicorp.com/terraform/cli/commands/test).

### 5.3 Linting, Style, and Review Discipline

- **Style guide first**: Follow HashiCorp's recommended naming, formatting, resource order, and file conventions
  - Shared conventions reduce cognitive load when dozens of modules and roots need maintenance; docs: [Style Guide](https://developer.hashicorp.com/terraform/language/style).
- **Static quality checks**: `terraform fmt` and `terraform validate` are the non-negotiable baseline
  - These are the cheapest checks with the highest signal-to-effort ratio; docs: [terraform fmt](https://developer.hashicorp.com/terraform/cli/commands/fmt), [terraform validate](https://developer.hashicorp.com/terraform/cli/commands/validate).
- **Third-party linting**: Tools like TFLint can enforce organization-specific rules
  - Terraform core does not ship a linter, so mature teams often add one for provider-specific and style-specific guardrails; docs: [Style Guide](https://developer.hashicorp.com/terraform/language/style), [TFLint](https://github.com/terraform-linters/tflint).
- **Plan review discipline**: Review plans like migrations, not like harmless diffs
  - The most important Terraform review skill is spotting destructive intent, accidental replacements, and environment boundary violations before apply.

### 5.4 Secrets and Sensitive Data Hygiene

- **State contains secrets**: Even redacted sensitive values often still exist in plan/state artifacts
  - This is why secret handling in Terraform is really a state-handling problem, not just a logging problem; docs: [Manage sensitive data](https://developer.hashicorp.com/terraform/language/manage-sensitive-data).
- **`sensitive` vs `ephemeral`**: `sensitive` hides values from output, while newer ephemeral features can omit supported values from state and plan files
  - Use this distinction carefully because many teams assume redaction equals non-persistence, and it does not; docs: [Manage sensitive data](https://developer.hashicorp.com/terraform/language/manage-sensitive-data).
- **Do not hardcode credentials**: Prefer environment variables, secure workspace variables, or dedicated secret systems
  - Secrets in Terraform code tend to leak into history, reviews, copied examples, and state faster than teams expect.
- **Access control around state**: Who can read state often effectively determines who can read your secrets
  - Treat state access with the same seriousness you would apply to production database credentials; docs: [Manage sensitive data](https://developer.hashicorp.com/terraform/language/manage-sensitive-data).

**Practice**: Add variable validation, preconditions or postconditions, a `check` block, and at least one `terraform test` case to a shared module. Then wire `fmt`, `validate`, and `test` into a CI workflow.

---

## Phase 6: Refactoring, Escape Hatches, and Real-World Change Patterns

### 6.1 Refactoring Without Breaking Infrastructure

- **Resource renames**: Use `moved` blocks when renaming resource labels or changing addresses
  - This is the right way to preserve infrastructure identity while improving code organization; docs: [moved block reference](https://developer.hashicorp.com/terraform/language/block/moved).
- **Module extraction**: Use `moved` blocks when pulling existing resources into a new child module
  - Module extraction is one of the most common production refactors, and doing it safely is a major Terraform maturity milestone.
- **Ownership changes**: Use `removed` blocks when Terraform should stop managing an object without destroying it
  - This is especially useful during handoffs, shared platform changes, or when ownership moves to another root or system; docs: [removed block reference](https://developer.hashicorp.com/terraform/language/block/removed).
- **Adopt before rewrite**: Import legacy infrastructure first, then refactor to cleaner code
  - Brownfield adoption usually goes better when you preserve working reality before trying to redesign everything; docs: [Import resources overview](https://developer.hashicorp.com/terraform/language/import).

### 6.2 Provisioners and Other Escape Hatches

- **Provisioners are a last resort**: Terraform strongly recommends purpose-built alternatives whenever possible
  - Provisioners make infrastructure harder to model predictably and often introduce brittle, partially managed side effects; docs: [Use provisioners](https://developer.hashicorp.com/terraform/language/provisioners), [Perform post-apply operations](https://developer.hashicorp.com/terraform/language/post-apply-operations).
- **Prefer image building, cloud-init, or configuration management**: Use tools designed for machine setup
  - Terraform is best at provisioning infrastructure objects, not at owning every post-boot script on every server; docs: [Perform post-apply operations](https://developer.hashicorp.com/terraform/language/post-apply-operations).
- **`terraform_data`**: Useful when you need lifecycle-aware glue without a real infrastructure resource
  - This is still an escape hatch, but it is often cleaner than abusing unrelated resources for side effects; docs: [terraform_data resource reference](https://developer.hashicorp.com/terraform/language/resources/terraform-data).
- **Local shell glue is operational debt**: Every `local-exec` is something future teammates must reason about outside normal Terraform graph semantics
  - Use it carefully and document why a better platform-native option was not possible.

### 6.3 Multi-environment and Repository Architecture

- **Split by blast radius**: Separate state when failure domains, ownership, or deployment cadence differ
  - Giant all-in-one states make plans noisy and failures costly; smaller boundaries are easier to reason about and recover.
- **Environment roots over giant conditionals**: Use separate roots when environments differ materially
  - Terraform stays more maintainable when topology differences are expressed through composition, not dozens of `var.is_prod` branches.
- **Shared modules, isolated state**: Reuse code aggressively, not state
  - This is a healthy default for platform teams: common modules underneath, environment-specific roots above.
- **Naming and tagging standards**: Centralize them in locals and module inputs
  - Consistent tags and names make drift analysis, cost attribution, policy checks, and incident response easier.

### 6.4 Reading Plans Like an Operator

- **Know what replacement looks like**: Some fields force recreation instead of in-place update
  - Provider docs and plan annotations together tell you when a "small" change is actually a destroy-and-create event.
- **Distinguish drift from desired change**: Unexpected plan output is often telling you about manual edits or provider defaults
  - Good operators do not just ask "Can we apply this?" but "Why does Terraform think this changed?"
- **Save and review destructive plans**: Especially for production
  - You want reviewers discussing one immutable plan artifact, not re-running plans against a moving environment.
- **Use `show -json` and policy tooling as you mature**: Structured plan data enables better automation
  - This is where Terraform starts becoming part of a larger governance and platform workflow; docs: [terraform show](https://developer.hashicorp.com/terraform/cli/commands/show).

**Practice**: Start with a flat, messy root module. Extract one reusable module, rename at least one resource safely with `moved`, replace one fragile provisioner with a better alternative, and prove the final refactor with a no-surprises plan.

---

## Phase 7: Team Workflows with HCP Terraform

### 7.1 HCP Terraform Essentials

- **What HCP Terraform is**: A hosted application for shared Terraform workflows, remote state, remote runs, access control, private registry, and policy integration
  - If local CLI workflows are Terraform's solo mode, HCP Terraform is the team operating model; docs: [What is HCP Terraform?](https://developer.hashicorp.com/terraform/cloud-docs).
- **Remote runs**: HCP Terraform can execute runs in a consistent remote environment
  - This reduces the risk of "my laptop had a different provider/plugin/environment setup" causing operational drift; docs: [HCP Terraform workspaces](https://developer.hashicorp.com/terraform/cloud-docs/workspaces), [Run modes and options](https://developer.hashicorp.com/terraform/cloud-docs/workspaces/run/modes-and-options).
- **Workspaces**: The unit that groups configuration, variables, state, and run history
  - HCP workspaces are effectively the operational home for a managed infrastructure collection; docs: [HCP Terraform workspaces](https://developer.hashicorp.com/terraform/cloud-docs/workspaces).
- **Projects and organization structure**: Group workspaces by ownership, domain, or platform boundaries
  - Good workspace organization becomes increasingly important as teams, policies, and environments multiply; docs: [HCP Terraform workspaces](https://developer.hashicorp.com/terraform/cloud-docs/workspaces).
- **Variable management**: Store Terraform variables and sensitive environment variables centrally
  - This is one of the cleanest ways to keep secrets out of local files and source control while keeping runs reproducible; docs: [HCP Terraform workspaces](https://developer.hashicorp.com/terraform/cloud-docs/workspaces).

### 7.2 Remote Execution Modes and Delivery Flow

- **VCS-driven workflow**: Connect workspaces to Git repositories so changes enter through reviewed commits and pull requests
  - This makes Terraform feel like the rest of modern software delivery rather than a collection of laptop commands; docs: [HCP Terraform workspaces](https://developer.hashicorp.com/terraform/cloud-docs/workspaces).
- **Speculative plans**: Preview infrastructure impact before merge
  - Speculative plans are one of the highest-value feedback loops in infrastructure review because they show real consequences early.
- **Apply approvals**: Keep a deliberate boundary between review and execution
  - Fast teams can still be safe teams if approvals, roles, and audited run history are part of the workflow.
- **Run modes**: Learn when to use remote execution, agent-based execution, or alternative modes
  - Execution location matters when private networking, compliance, or provider connectivity requirements enter the picture; docs: [Run modes and options](https://developer.hashicorp.com/terraform/cloud-docs/workspaces/run/modes-and-options).

### 7.3 Governance, Drift Detection, and Continuous Validation

- **Policy enforcement**: HCP Terraform supports policy-as-code with Sentinel and OPA
  - This is how organizations turn naming standards, network restrictions, cost rules, or compliance rules into enforceable gates on Terraform runs; docs: [Manage policy sets](https://developer.hashicorp.com/terraform/cloud-docs/workspaces/policy-enforcement/manage-policy-sets), [Define OPA policies](https://developer.hashicorp.com/terraform/cloud-docs/workspaces/policy-enforcement/define-policies/opa).
- **Enforcement levels**: Advisory, soft-mandatory, mandatory, and related policy behaviors shape how strict your platform is
  - The right policy mode depends on whether you are educating, warning, or hard-blocking; docs: [Manage policy sets](https://developer.hashicorp.com/terraform/cloud-docs/workspaces/policy-enforcement/manage-policy-sets).
- **Health assessments**: HCP Terraform can detect drift and continuous validation failures over time
  - This matters because infrastructure can become non-compliant long after a successful apply due to manual edits, defaults, or external change; docs: [HCP Terraform workspaces](https://developer.hashicorp.com/terraform/cloud-docs/workspaces), [Health assessments](https://developer.hashicorp.com/terraform/cloud-docs/workspaces/health).
- **Drift detection**: Identify when real infrastructure no longer matches configured intent
  - Drift detection gives teams visibility into out-of-band changes before the next emergency plan surprises them; docs: [Health assessments](https://developer.hashicorp.com/terraform/cloud-docs/workspaces/health).
- **Continuous validation**: Keep checking whether your custom conditions still hold after provisioning
  - This extends Terraform from "provision correctly once" toward "keep infrastructure aligned over time"; docs: [HCP Terraform workspaces](https://developer.hashicorp.com/terraform/cloud-docs/workspaces), [Validate your configuration](https://developer.hashicorp.com/terraform/language/validate).

### 7.4 Private Registry and Shared Platform Work

- **Private module registry**: Distribute internal modules with clearer versioning and consumption patterns
  - Internal reuse gets dramatically better when module publishing is treated like package publishing instead of copy-paste sharing; docs: [What is HCP Terraform?](https://developer.hashicorp.com/terraform/cloud-docs).
- **Shared platform contracts**: Platform teams can publish modules, variables, and policies while application teams consume them through controlled interfaces
  - This is often where Terraform becomes a real platform capability instead of just a tool individual engineers happen to know.

**Practice**: Take one working root module and move it into an HCP Terraform workspace with VCS-driven plans, sensitive variables, a basic policy set, and health assessments enabled where available.

---

## Phase 8: Debugging, Scale, and Production Judgment

### 8.1 Common Failure Modes

- **Authentication and credentials problems**: Providers fail when runtime credentials are missing, expired, or scoped incorrectly
  - Credential issues often look like Terraform issues at first, but the real problem is usually provider auth or execution context.
- **Provider version mismatches**: Different plugin versions can change schema, defaults, and plan behavior
  - This is exactly why version constraints and lock files deserve so much attention in Terraform repos; docs: [Provider Requirements](https://developer.hashicorp.com/terraform/language/providers/requirements), [Dependency Lock File](https://developer.hashicorp.com/terraform/language/files/dependency-lock).
- **Dependency cycles**: Over-coupled resources or data lookups can make the graph impossible to resolve
  - Cycles usually mean the architecture needs a cleaner boundary or a split into separate layers/states.
- **Imported configuration mismatch**: Imported state and handwritten config can disagree badly
  - Import success does not mean "done"; it means "Terraform now knows about the object, now make the code match reality."
- **Manual drift**: Out-of-band changes create surprising future plans
  - Drift is not a Terraform bug; it is Terraform telling you the actual world changed out from under the declared one.

### 8.2 Performance and Scale

- **Split large states by ownership and lifecycle**: Smaller roots plan faster and fail more safely
  - Massive monolithic states create noisy diffs, slower runs, and higher recovery stress.
- **Keep modules focused**: Deeply nested abstraction stacks make plans and reviews harder
  - Some abstraction is good; too much abstraction turns infrastructure review into archaeology.
- **Limit unnecessary data source lookups**: Query only what you truly need
  - Excessive discovery logic increases fragility and often hides implicit dependencies.
- **Be aware of provider API rate limits and eventual consistency**: Terraform is only as reliable as the APIs it orchestrates
  - Production Terraform skill includes understanding the operational behavior of the target platform, not just HCL syntax.

### 8.3 When Terraform Is the Wrong Tool

- **Application deployment orchestration**: Terraform is usually not the best place to model frequent app rollout state
  - Use Terraform to provision the platform and deployment system, not to own every app release toggle.
- **Machine configuration drift**: Use image building, cloud-init, or config management for deep host customization
  - Terraform can provision the VM; it should not become your fragile SSH scripting framework; docs: [Perform post-apply operations](https://developer.hashicorp.com/terraform/language/post-apply-operations).
- **High-churn operational data**: Terraform is poor for values that change constantly and are not true infrastructure configuration
  - If the data changes faster than you want to review plans, it probably does not belong in Terraform state.
- **One-off imperative tasks**: Terraform is not a general-purpose automation runner
  - Force-fitting imperative jobs into resource lifecycles usually creates confusing state and brittle workflows.

### 8.4 Production Habits That Matter Most

- **Review every plan**: Especially replacements and deletes
  - The most expensive Terraform mistakes are usually visible in the plan first.
- **Pin versions and commit the lock file**: Make change intentional
  - Surprise upgrades are the opposite of safe infrastructure operations.
- **Keep state secure and backed up**: Infrastructure history matters
  - Recovery is much easier when state storage, access, and history are treated as first-class operational concerns.
- **Practice imports and refactors before you need them in anger**: Migration skill is not optional in real environments
  - Most mature Terraform work happens in brownfield systems, not blank greenfield demos.

**Practice**: Perform a deliberate incident drill. Introduce controlled drift in a sandbox, inspect the next plan, decide whether to revert or codify the drift, and document the operational reasoning behind your choice.

---

## Capstone Projects

Build these to demonstrate job-ready Terraform skills:

### Project 1: Production-style AWS or Azure Foundation

- Networking layer with public and private subnets
  - This proves you can model foundational infrastructure with stable boundaries rather than only single-resource demos.
- IAM or RBAC primitives, security groups / NSGs, and tagging standards
  - Access control and naming discipline are part of real Terraform work, not optional polish.
- Remote state backend or HCP Terraform workspace
  - A serious capstone should use team-grade state handling, not local-only workflows.
- Reusable `network`, `compute`, and `database` modules
  - This demonstrates that you understand module boundaries and environment assembly.
- CI checks for `fmt`, `validate`, and at least one `terraform test`
  - Shipping Terraform without automated quality gates is a missed opportunity to show engineering maturity.

### Project 2: Multi-environment Platform Stack

- Separate `dev`, `staging`, and `prod` roots that call shared modules
  - This shows you understand the difference between code reuse and state reuse.
- Centralized naming, tags, and policy-relevant metadata via locals and module inputs
  - Mature infrastructure teams care about consistency because compliance, costs, and operations depend on it.
- Shared module versioning and upgrade process
  - This is where Terraform starts looking like platform engineering rather than repo-by-repo scripting.
- HCP Terraform with VCS-driven runs, sensitive variables, and approval flow
  - Remote workflow literacy is a major differentiator in real teams.
- Policy enforcement for one or two guardrails such as mandatory tags or blocked instance types
  - Governance is an important part of professional Terraform work; docs: [Manage policy sets](https://developer.hashicorp.com/terraform/cloud-docs/workspaces/policy-enforcement/manage-policy-sets).

### Project 3: Brownfield Adoption and Refactor

- Import existing infrastructure into Terraform management
  - This is one of the most realistic Terraform projects because many teams adopt Terraform after infrastructure already exists.
- Cleanly model imported resources with typed variables, outputs, and modules
  - Import alone is not enough; the final code still needs to be maintainable.
- Use `moved` blocks to refactor resource addresses without replacement
  - This proves you understand state-safe refactoring and not just fresh builds.
- Remove one resource from Terraform control intentionally with `removed`
  - Ownership changes happen in real platforms, and safe offboarding matters too.
- Write a short runbook for plan review, apply approval, rollback thinking, and drift handling
  - Professional Terraform skill includes operator judgment, not just syntax knowledge.

---

## Study Methodology

1. **Use the official docs as the textbook and this guide as the roadmap**
   - Terraform core is smaller than many people think; most mastery comes from systematically reading the official language, CLI, state, and provider docs. Start with the pages that match your current phase; docs: [Terraform Language](https://developer.hashicorp.com/terraform/language), [Terraform CLI](https://developer.hashicorp.com/terraform/cli).
2. **Start with one provider and one cloud or platform**
   - The Terraform mental model is easier to learn when provider semantics are not changing under you at the same time.
3. **Review every plan line by line**
   - Plan reading is the core operational skill. Do not outsource your understanding of replacements, destroys, and drift.
4. **Treat state as critical infrastructure data**
   - Once you internalize that state is sensitive, shared, and operationally central, your Terraform habits get much better fast; docs: [State](https://developer.hashicorp.com/terraform/language/state), [Manage sensitive data](https://developer.hashicorp.com/terraform/language/manage-sensitive-data).
5. **Build a module only after you have written the pattern twice**
   - Premature abstraction is as harmful in Terraform as it is in application code.
6. **Practice brownfield workflows early**
   - Imports, refactors, and drift remediation are not edge cases; they are the daily reality of mature infrastructure teams; docs: [Import resources overview](https://developer.hashicorp.com/terraform/language/import), [moved block reference](https://developer.hashicorp.com/terraform/language/block/moved).
7. **Add validation and tests before your modules become widely shared**
   - It is much easier to encode assumptions early than to retrofit contracts after multiple teams already depend on unclear behavior; docs: [Validate your configuration](https://developer.hashicorp.com/terraform/language/validate), [terraform test](https://developer.hashicorp.com/terraform/cli/commands/test).
8. **Learn HCP Terraform after you are comfortable with local CLI workflows**
   - Remote runs, policies, drift detection, and private registries make more sense once the core Terraform workflow is already intuitive; docs: [What is HCP Terraform?](https://developer.hashicorp.com/terraform/cloud-docs), [HCP Terraform workspaces](https://developer.hashicorp.com/terraform/cloud-docs/workspaces).

---

## Additional Reference Links

- **Terraform core references**:
  - [Terraform Language](https://developer.hashicorp.com/terraform/language)
  - [Terraform CLI](https://developer.hashicorp.com/terraform/cli)
  - [Terraform Workflow](https://developer.hashicorp.com/terraform/cli/run)
  - [Style Guide](https://developer.hashicorp.com/terraform/language/style)
- **Configuration references**:
  - [terraform block reference](https://developer.hashicorp.com/terraform/language/block/terraform)
  - [resource block reference](https://developer.hashicorp.com/terraform/language/block/resource)
  - [Data Sources](https://developer.hashicorp.com/terraform/language/data-sources)
  - [Variables](https://developer.hashicorp.com/terraform/language/values/variables)
  - [Locals](https://developer.hashicorp.com/terraform/language/values/locals)
  - [Outputs](https://developer.hashicorp.com/terraform/language/values/outputs)
  - [Expressions](https://developer.hashicorp.com/terraform/language/expressions)
  - [Functions](https://developer.hashicorp.com/terraform/language/functions)
  - [Meta-arguments](https://developer.hashicorp.com/terraform/language/meta-arguments)
- **State, testing, and refactoring references**:
  - [State](https://developer.hashicorp.com/terraform/language/state)
  - [Manage sensitive data](https://developer.hashicorp.com/terraform/language/manage-sensitive-data)
  - [Import resources overview](https://developer.hashicorp.com/terraform/language/import)
  - [moved block reference](https://developer.hashicorp.com/terraform/language/block/moved)
  - [removed block reference](https://developer.hashicorp.com/terraform/language/block/removed)
  - [Tests](https://developer.hashicorp.com/terraform/language/tests)
  - [terraform test](https://developer.hashicorp.com/terraform/cli/commands/test)
- **Modules and team workflow references**:
  - [Modules overview](https://developer.hashicorp.com/terraform/language/modules)
  - [Creating Modules](https://developer.hashicorp.com/terraform/language/modules/develop)
  - [Module Composition](https://developer.hashicorp.com/terraform/language/modules/develop/composition)
  - [What is HCP Terraform?](https://developer.hashicorp.com/terraform/cloud-docs)
  - [HCP Terraform workspaces](https://developer.hashicorp.com/terraform/cloud-docs/workspaces)
  - [Run modes and options](https://developer.hashicorp.com/terraform/cloud-docs/workspaces/run/modes-and-options)
  - [Manage policy sets](https://developer.hashicorp.com/terraform/cloud-docs/workspaces/policy-enforcement/manage-policy-sets)
  - [Health assessments](https://developer.hashicorp.com/terraform/cloud-docs/workspaces/health)
- **Learning resources**:
  - [Terraform Tutorials](https://developer.hashicorp.com/terraform/tutorials)
  - [Terraform Registry](https://registry.terraform.io/)
  - [HashiCorp Certifications](https://developer.hashicorp.com/certifications)
