# Testing Study Guide

A depth-first guide to software testing for working engineers. It covers the testing mental model, the major testing methodologies, and practical testing in Python, Node.js, and Go. It also treats testing as an enterprise engineering system: how teams choose a test portfolio, keep pipelines fast, manage flaky tests, test distributed systems, and turn quality from a late QA phase into a continuous feedback loop.

The throughline is simple: **tests are executable confidence**. They are not paperwork, they are not a coverage number, and they are not a substitute for design. A good test suite tells you whether the software still keeps its promises after you changed it. A great test strategy tells you which promises matter most, where to check them, and how quickly the right person gets useful feedback.

This guide pairs naturally with the [GitHub Actions guide](GITHUB_ACTIONS_STUDY_GUIDE.md), [Observability guide](OBSERVABILITY_STUDY_GUIDE.md), [Distributed Systems guide](DISTRIBUTED_SYSTEMS_STUDY_GUIDE.md), [Advanced Python guide](ADVANCED_PYTHON_STUDY_GUIDE.md), [Advanced Node.js guide](ADVANCED_NODEJS_STUDY_GUIDE.md), and [Advanced Go guide](ADVANCED_GO_STUDY_GUIDE.md). Testing is where those disciplines meet: runtime behavior, CI, observability, security, performance, and team ownership.

Primary references: the Python [`unittest`](https://docs.python.org/3/library/unittest.html) and [`unittest.mock`](https://docs.python.org/3/library/unittest.mock.html) docs, [pytest](https://docs.pytest.org/en/stable/), [Hypothesis](https://hypothesis.readthedocs.io/en/latest/), [coverage.py](https://coverage.readthedocs.io/), the Node.js [`node:test`](https://nodejs.org/api/test.html) docs, [Jest](https://jestjs.io/docs/getting-started), [Vitest](https://vitest.dev/), [fast-check](https://fast-check.dev/), the Go [`testing`](https://pkg.go.dev/testing) package, the Go [fuzzing](https://go.dev/doc/security/fuzz/) docs, the Go [race detector](https://go.dev/doc/articles/race_detector), [Playwright](https://playwright.dev/), [Cypress](https://docs.cypress.io/app/get-started/why-cypress), Martin Fowler's [Practical Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html), Microsoft's [shift-left testing principles](https://learn.microsoft.com/en-us/devops/develop/shift-left-make-testing-fast-reliable), and the [OWASP Web Security Testing Guide](https://owasp.org/www-project-web-security-testing-guide/latest/).

---

## Table of Contents

1. [Part 1 - The Mental Model](#part-1-the-mental-model)
2. [Part 2 - The Test Portfolio](#part-2-the-test-portfolio)
3. [Part 3 - Writing Tests That Survive Refactoring](#part-3-writing-tests-that-survive-refactoring)
4. [Part 4 - Test Doubles, Boundaries, and Isolation](#part-4-test-doubles-boundaries-and-isolation)
5. [Part 5 - Python Testing](#part-5-python-testing)
6. [Part 6 - Node.js Testing](#part-6-nodejs-testing)
7. [Part 7 - Go Testing](#part-7-go-testing)
8. [Part 8 - Methodologies and Specialized Testing](#part-8-methodologies-and-specialized-testing)
9. [Part 9 - Distributed and Non-Deterministic Systems](#part-9-distributed-and-non-deterministic-systems)
10. [Part 10 - Enterprise Testing Strategy](#part-10-enterprise-testing-strategy)
11. [Part 11 - CI/CD, Test Selection, and Feedback Loops](#part-11-cicd-test-selection-and-feedback-loops)
12. [Part 12 - Legacy Systems](#part-12-legacy-systems)
13. [Part 13 - Recipes and Checklists](#part-13-recipes-and-checklists)

---

## Part 1 - The Mental Model

Testing is not one activity. It is a family of feedback loops.

Some tests answer "does this pure function handle the edge case?" Some answer "does this service still honor the API contract?" Some answer "can a user complete checkout?" Some answer "does the system degrade safely when Redis is down?" Some answer "did we accidentally reintroduce a security weakness?" They all matter, but they should not all run at the same time, cost the same amount, or block the same decisions.

### The Four Questions Every Test Answers

Every test has four parts, whether you write them explicitly or not:

1. **Subject** - what behavior is under test?
2. **Scenario** - under what conditions?
3. **Oracle** - how do we know whether the result is correct?
4. **Feedback channel** - who receives the failure, when, and with what context?

Weak tests usually fail in one of these four places. The subject is too broad, the scenario is accidental, the oracle only checks implementation trivia, or the failure arrives too late to be useful.

### Tests Are Not Proofs

Tests sample behavior. They do not prove correctness in the mathematical sense. A test suite gives confidence because it combines many imperfect signals:

- examples for known business cases,
- edge cases for boundaries,
- properties for broad input spaces,
- integration checks for wiring,
- contract checks for service boundaries,
- E2E checks for critical user journeys,
- static analysis for whole-codebase rules,
- runtime monitoring for the messy truth of production.

This matters because the goal is not "write every possible test." The goal is **buy the most confidence per unit of cost**.

### The Cost Model

A test has at least five costs:

| Cost | Meaning | Typical cause |
|---|---|---|
| Authoring | Time to write it | unclear requirements, bad test utilities |
| Runtime | Time to execute it | database, browser, network, slow setup |
| Maintenance | Time to update it after safe changes | implementation-coupled assertions |
| Diagnosis | Time to understand a failure | vague names, huge fixtures, noisy logs |
| Trust | Confidence lost when tests are flaky or irrelevant | nondeterminism, shared state, false positives |

The highest-value test is not always the smallest one. It is the test whose failure changes a decision. If a test fails and everyone ignores it, it is not a safety net; it is background noise.

### The Testing Vocabulary

Definitions vary across organizations, so be explicit. This guide uses:

| Term | Meaning |
|---|---|
| Unit test | Tests one small behavior in isolation, usually no real network, filesystem, database, or clock dependency. |
| Integration test | Tests two or more real components together, often including database, queue, filesystem, or external protocol boundary. |
| Component test | Tests a deployable component through its public interface while replacing outside services. |
| Contract test | Tests whether a provider and consumer agree on request/response/event shape and semantics. |
| End-to-end test | Tests a realistic user or system journey across the whole stack. |
| Functional test | Tests externally visible behavior, regardless of internal structure. |
| Regression test | Captures a bug so it stays fixed. |
| Smoke test | Small check that a build or deployment is basically alive. |
| Characterization test | Describes current behavior of legacy code before changing it. |
| Property-based test | Generates many inputs and checks an invariant that should always hold. |
| Fuzz test | Mutates or generates inputs to find crashes, panics, hangs, parser bugs, or security issues. |
| Mutation test | Changes production code automatically to see whether tests catch the change. |
| Exploratory test | Human investigation using skill, curiosity, and product knowledge. |

The terminology matters less than the portfolio. A team arguing about whether a test is "integration" or "component" is usually avoiding the real questions: what risk does it cover, where should it run, and who owns it?

### The Testing Loop

The ideal loop is:

1. Understand the behavior.
2. Choose the cheapest level that can prove that behavior.
3. Make the system testable.
4. Write the test with a clear oracle.
5. Run it locally and in CI.
6. Use failures to improve either product code, test code, or requirements.

When testing feels painful, do not only ask "how do I mock this?" Ask "why is this behavior hard to observe?" Hard-to-test code often reveals hidden design problems: global state, time calls embedded everywhere, tangled I/O, giant methods, implicit dependencies, or unclear ownership boundaries.

---

## Part 2 - The Test Portfolio

The classic test pyramid is still useful if you treat it as an economic model, not a law of nature: many small fast tests, fewer medium tests, very few broad slow tests. The reason is not ideology; it is cost. Broad tests are slower, harder to diagnose, and more likely to fail for reasons unrelated to the code you changed.

### The Practical Test Pyramid

```text
          E2E / journeys
       contract / component
    integration / API / DB
 unit / property / static checks
```

The lower layers should be:

- fast enough to run constantly,
- deterministic,
- specific in failure messages,
- owned by the developers changing the code.

The upper layers should be:

- focused on critical paths,
- closer to user or business value,
- resilient to harmless implementation changes,
- instrumented enough to diagnose failures.

### The Test Trophy

Frontend teams sometimes prefer the "testing trophy":

```text
        E2E
   integration/component
        unit
       static
```

The point is that static analysis catches a lot in TypeScript-heavy apps, and component/integration tests often give better value than tiny implementation-level unit tests. This is not a contradiction of the pyramid. It is the same economic idea applied to UI code: test behavior at the level where it is stable and meaningful.

### A Useful Portfolio for Services

For a backend service, a healthy portfolio often looks like:

| Layer | Purpose | Local? | PR gate? | Nightly? |
|---|---|---:|---:|---:|
| Formatting/lint/type/static | Catch cheap whole-codebase problems | yes | yes | yes |
| Unit tests | Business rules, data transforms, edge cases | yes | yes | yes |
| Property/fuzz tests | Broad input-space bugs | some | bounded subset | longer run |
| Integration tests | DB migrations, repositories, queues, serialization | yes, via containers | yes, selected | yes |
| Contract tests | Service boundary compatibility | sometimes | yes | yes |
| Component tests | Service through API with fake dependencies | sometimes | yes | yes |
| E2E tests | Critical journeys across real stack | rarely | smoke subset | full suite |
| Performance/security | Non-functional regression | targeted | targeted | scheduled |
| Production checks | Synthetic journeys, canaries, SLOs | no | deploy gate | continuous |

The art is in deciding where each behavior belongs.

### Choosing the Right Level

Use the cheapest test that can fail for the right reason.

| Behavior | Best first test |
|---|---|
| Pure calculation or validation | Unit or property test |
| Database query correctness | Integration test with real DB |
| API serialization shape | Component or contract test |
| Consumer/provider compatibility | Contract test |
| Retry/backoff logic | Unit test with fake clock and fake dependency |
| Queue processing idempotency | Integration plus property/invariant tests |
| Browser interaction | Component test or E2E test |
| Permission boundary | Unit for policy, integration/E2E for enforcement path |
| Deployment wiring | Smoke test and synthetic check |
| Race condition | Stress test, race detector, deterministic scheduler where possible |
| Security control | Unit for helper, integration/security test for exploit path |

### The Anti-Portfolio

Common unhealthy shapes:

| Shape | Symptom | Fix |
|---|---|---|
| Ice cream cone | Many manual/E2E tests, few unit/integration tests | Push behavior down into unit/component tests. |
| Hourglass | Many tiny unit tests and many E2E tests, little integration | Add API, DB, contract, and component tests. |
| Screenshot wall | Massive visual snapshots fail constantly | Assert meaningful user-visible states; use visual tests sparingly. |
| Mock forest | Unit tests mock every collaborator and verify calls | Test observable behavior; move mocks to process/network boundaries. |
| Coverage theater | High line coverage, low defect detection | Add branch, edge, property, and mutation checks. |
| Flake swamp | Failures are rerun instead of fixed | Quarantine briefly, assign owner, track flake rate. |

### Coverage Is a Map, Not a Goal

Coverage tells you what code ran. It does not tell you whether assertions were meaningful.

Useful coverage practices:

- measure branch coverage, not only line coverage;
- fail PRs on meaningful drops, not arbitrary organization-wide numbers;
- inspect uncovered high-risk code manually;
- require regression tests for bug fixes;
- exclude generated code and unreachable defensive paths intentionally;
- combine coverage with mutation testing for critical libraries.

Bad coverage practices:

- chasing 100 percent across all code,
- writing tests that execute code without assertions,
- using coverage as a developer performance metric,
- blocking important refactors on low-value lines.

Coverage is best used as a flashlight. It shows dark corners. It does not tell you whether the building is safe.

---

## Part 3 - Writing Tests That Survive Refactoring

Good tests care about behavior. Fragile tests care about incidental implementation.

### The Shape of a Good Test

Most tests should read as:

```text
Given this state
When this behavior happens
Then this observable result is true
```

In code, this is often Arrange/Act/Assert:

```python
def test_discount_applies_to_enterprise_accounts():
    account = Account(plan="enterprise")
    invoice = Invoice(subtotal_cents=10_000)

    total = price_invoice(account, invoice)

    assert total.cents == 8_000
```

The structure is boring in the best way. A future reader can see the scenario, action, and expected outcome without reverse-engineering a fixture maze.

### Test Names Are Documentation

Prefer names that say behavior:

```text
test_rejects_expired_token
test_preserves_order_when_priorities_are_equal
test_retries_transient_502_once_then_succeeds
test_does_not_charge_card_when_inventory_reservation_fails
```

Avoid names that only mirror methods:

```text
test_validate
test_process
test_handler
test_success
```

A failure should be readable in CI without opening the file.

### One Test, One Reason to Fail

"One assertion per test" is too rigid. A test may need several assertions to describe one behavior. The better rule is **one reason to fail**.

Good:

```python
def test_successful_signup_returns_user_and_sends_welcome_email():
    result = signup(email="a@example.com")

    assert result.user.email == "a@example.com"
    assert result.user.status == "active"
    assert email_outbox.last().template == "welcome"
```

Weak:

```python
def test_signup():
    # creates user, validates password, sends email, writes audit log,
    # handles duplicate email, handles invalid email, checks metrics...
```

If a test needs a long comment explaining what it covers, split it.

### Prefer Observable Behavior

Testing private methods is usually a design smell. If a private method contains complex behavior worth testing independently, extract a smaller public unit in the same package/module boundary.

Behavior-oriented tests survive refactoring:

```python
assert cart.total_cents() == 4200
```

Implementation-coupled tests break when safe refactors happen:

```python
tax_calculator.calculate.assert_called_once_with(cart.items)
discount_service.apply.assert_called_once()
```

Call assertions are useful at true boundaries: sending an email, publishing an event, writing a metric, charging a card. They are weaker inside the domain core.

### Make Data Small and Explicit

Test data should be as small as possible while still expressing the behavior.

Bad:

```json
{
  "user": {
    "id": "u_123",
    "name": "Jane",
    "timezone": "America/Chicago",
    "marketingPreferences": { "...": "..." },
    "roles": ["admin", "editor", "billing"],
    "features": { "...": "..." }
  }
}
```

Good:

```python
user = User(role="billing_admin")
```

If real objects are large, use builders:

```python
user = a_user().with_role("billing_admin").build()
invoice = an_invoice().past_due().for_user(user).build()
```

Builders make important data visible and irrelevant data defaulted.

### Control Time, Randomness, and External State

The three classic sources of flakiness:

- time,
- randomness,
- shared mutable state.

Design code so tests can inject:

- a clock,
- an ID generator,
- a random number generator,
- a filesystem path,
- a database transaction,
- a network client,
- environment/config values.

Bad:

```python
def issue_token(user_id):
    return Token(user_id=user_id, expires_at=datetime.now() + timedelta(hours=1))
```

Good:

```python
def issue_token(user_id, *, now):
    return Token(user_id=user_id, expires_at=now + timedelta(hours=1))
```

This small design choice removes sleeps, timezone surprises, DST bugs, and test races.

### Avoid Sleeping in Tests

Sleeping is usually a guess disguised as synchronization.

Bad:

```javascript
await submit()
await new Promise(resolve => setTimeout(resolve, 1000))
expect(await status()).toBe('complete')
```

Better:

```javascript
await submit()
await expect.poll(() => status()).toBe('complete')
```

Or design the code to expose a deterministic signal: event, promise, channel, callback, queue drain, fake clock, or observable state transition.

### Use Snapshots Carefully

Snapshot tests are good when:

- the output is large but meaningful,
- humans review changes carefully,
- the output is stable,
- the snapshot is close to a public contract.

Snapshot tests are bad when:

- they capture incidental markup,
- they change on every refactor,
- reviewers blindly approve updates,
- they replace semantic assertions.

Golden files in Go, approval tests for generated documents, and frontend snapshots all have the same rule: **review the diff like production code**.

### Failure Messages Matter

A useful failure says:

- what scenario failed,
- what value was expected,
- what value was observed,
- where to look next.

For complex checks, custom assertion helpers are worth it:

```go
func assertInvoiceTotal(t *testing.T, got Invoice, wantCents int64) {
	t.Helper()
	if got.TotalCents != wantCents {
		t.Fatalf("invoice total: got %d cents, want %d cents; invoice=%+v",
			got.TotalCents, wantCents, got)
	}
}
```

The `t.Helper()` call makes Go report the caller's line instead of the helper's line. Every language has some version of this idea: write helpers that improve diagnosis, not helpers that hide the scenario.

---

## Part 4 - Test Doubles, Boundaries, and Isolation

Test doubles replace a dependency during a test. They are powerful, but easy to overuse.

### The Five Test Doubles

| Double | Purpose | Example |
|---|---|---|
| Dummy | Passed only because the API requires it | `None`, empty logger |
| Stub | Returns canned data | fake exchange rate client returns 1.25 |
| Fake | Working simplified implementation | in-memory repository |
| Spy | Records calls for later inspection | email sender records sent messages |
| Mock | Pre-programmed expectation about calls | assert payment gateway called once |

Many teams call all of these "mocks." That is fine casually, but the distinctions help you choose the right tool.

### Mock Roles, Not Objects

Mocking works best at role boundaries:

- payment gateway,
- email sender,
- object storage,
- clock,
- event publisher,
- third-party API,
- feature flag client.

Mocking works poorly when it mirrors every internal class:

```text
OrderService -> DiscountService -> TaxService -> InventoryService -> AuditService
```

If a unit test requires five internal mocks, the unit may be too large or the test may be asserting implementation. Try extracting pure domain logic and writing one integration/component test around the orchestration.

### The Dependency Boundary Rule

Use real collaborators inside your boundary. Replace collaborators outside your boundary.

For example, in a billing service:

- use real invoice calculation,
- use real tax classification logic,
- use a fake clock,
- use a fake payment gateway,
- use a test database for persistence integration,
- use a fake or contract-verified external accounting API.

This keeps business logic real while preventing tests from charging cards, sending emails, or depending on external uptime.

### Fakes Beat Mocks When Behavior Matters

A fake can model behavior over time:

```python
class FakeEmailSender:
    def __init__(self):
        self.sent = []

    def send(self, *, to, template, data):
        self.sent.append({"to": to, "template": template, "data": data})
```

This lets tests assert outcomes:

```python
assert fake_email.sent[-1]["template"] == "welcome"
```

Fakes are especially useful for repositories, queues, caches, and service clients. But do not let fakes become separate products. If the fake has complex behavior, also test against the real dependency somewhere.

### Contract Tests Keep Doubles Honest

Every fake can drift from reality. Contract tests reduce that risk.

Provider contract:

- "POST /payments requires amount and idempotency key."
- "Duplicate idempotency key returns same result."
- "Card declined returns 402 with code `card_declined`."

Consumer contract:

- "Billing service sends idempotency key."
- "Billing service handles 402 as non-retryable."
- "Billing service retries 502 but not 400."

Tools vary by stack: Pact, Spring Cloud Contract, protobuf/gRPC compatibility checks, OpenAPI schema checks, AsyncAPI event checks, and homegrown contract suites can all work. The key is to test the boundary as a shared asset, not as folklore.

### Patch Where Looked Up

In dynamic languages, mocking often fails because the wrong symbol is patched.

If code does:

```python
# billing/service.py
from billing.gateway import charge

def bill(invoice):
    return charge(invoice)
```

Patch `billing.service.charge`, not `billing.gateway.charge`, because `bill()` looks up the name in `billing.service`.

The equivalent in Node is understanding whether the code imports a function once, captures it in a closure, reads it from a module object each call, or receives it through dependency injection. Testability improves dramatically when dependencies are passed explicitly.

---

## Part 5 - Python Testing

Python has a standard-library testing stack and a dominant third-party testing style:

- `unittest` is built in, class-based, xUnit-style, and still common in mature codebases.
- `unittest.mock` is built in and widely used for patching, mocks, spies, and async mocks.
- `pytest` is the default choice for many modern Python projects because plain `assert`, fixtures, parametrization, and plugin support make tests concise.
- `Hypothesis` is the property-based testing library to know.
- `coverage.py` is the standard coverage engine.

### Recommended Python Stack

For most application teams:

```text
pytest
pytest-cov or coverage.py
unittest.mock
Hypothesis for property tests
pytest-xdist for parallelism when useful
pytest-asyncio or anyio for async tests
testcontainers or Docker Compose for integration dependencies
```

For libraries with no test dependencies, `unittest` is still perfectly valid. For enterprise teams, consistency matters more than framework fashion.

### Project Layout

A typical layout:

```text
project/
  pyproject.toml
  src/
    billing/
      __init__.py
      invoice.py
      service.py
  tests/
    unit/
      test_invoice.py
    integration/
      test_invoice_repository.py
    contract/
      test_payment_gateway_contract.py
```

In `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"
markers = [
  "integration: tests that require external services",
  "contract: service boundary compatibility tests",
  "slow: tests too slow for the default local loop",
]
```

Run:

```bash
pytest
pytest tests/unit
pytest -m "not integration and not slow"
pytest -m integration
coverage run -m pytest
coverage report -m
coverage html
```

### Plain pytest Test

```python
# src/billing/discounts.py
from dataclasses import dataclass

@dataclass(frozen=True)
class Customer:
    tier: str

def discount_rate(customer: Customer) -> float:
    if customer.tier == "enterprise":
        return 0.20
    if customer.tier == "pro":
        return 0.10
    return 0.0
```

```python
# tests/unit/test_discounts.py
from billing.discounts import Customer, discount_rate

def test_enterprise_customers_receive_twenty_percent_discount():
    assert discount_rate(Customer(tier="enterprise")) == 0.20
```

pytest rewrites `assert` statements to show useful diffs. Use plain `assert` unless you need a custom helper.

### Parametrization

Use parametrization when the behavior is the same and the data varies:

```python
import pytest

from billing.discounts import Customer, discount_rate

@pytest.mark.parametrize(
    ("tier", "expected"),
    [
        ("enterprise", 0.20),
        ("pro", 0.10),
        ("free", 0.0),
        ("unknown", 0.0),
    ],
)
def test_discount_rates_by_customer_tier(tier, expected):
    assert discount_rate(Customer(tier=tier)) == expected
```

Do not over-parametrize unrelated scenarios. A huge table with ten columns is a spreadsheet, not a readable test.

### Fixtures

Fixtures provide setup and teardown:

```python
import pytest

from billing.repository import InvoiceRepository

@pytest.fixture
def invoice_repo(tmp_path):
    db_path = tmp_path / "invoices.sqlite3"
    repo = InvoiceRepository.connect(db_path)
    repo.migrate()
    return repo

def test_saves_and_loads_invoice(invoice_repo):
    invoice_repo.save(invoice_id="inv_1", total_cents=4200)

    loaded = invoice_repo.get("inv_1")

    assert loaded.total_cents == 4200
```

Good fixtures are:

- local to the tests that need them,
- named after the resource they provide,
- small,
- deterministic,
- explicit about expensive work.

Avoid autouse fixtures unless they enforce a global invariant like clearing environment variables or resetting a shared registry. Hidden setup is one of the fastest ways to make tests mysterious.

### Monkeypatching Environment and Globals

```python
def test_reads_api_url_from_environment(monkeypatch):
    monkeypatch.setenv("PAYMENTS_URL", "https://payments.test")

    assert load_config().payments_url == "https://payments.test"
```

`monkeypatch` automatically restores changes after the test. Prefer it over manually mutating `os.environ`.

### Mocking with `unittest.mock`

Use `Mock`, `MagicMock`, `AsyncMock`, and `patch` for true boundaries.

```python
from unittest.mock import Mock

from billing.service import BillingService

def test_declined_payment_does_not_mark_invoice_paid():
    gateway = Mock()
    gateway.charge.return_value = {"status": "declined", "code": "card_declined"}
    repo = FakeInvoiceRepository()
    service = BillingService(repo=repo, payment_gateway=gateway)

    result = service.pay("inv_1")

    assert result.status == "declined"
    assert repo.get("inv_1").status == "open"
    gateway.charge.assert_called_once()
```

Prefer dependency injection like this over patching module globals. It makes tests clearer and production code more modular.

When patching is necessary:

```python
from unittest.mock import patch

@patch("billing.service.charge_card")
def test_charges_card(mock_charge_card):
    mock_charge_card.return_value = {"status": "ok"}

    result = pay_invoice("inv_1")

    assert result.status == "paid"
    mock_charge_card.assert_called_once()
```

Remember: patch where the code under test looks up the name.

### Async Python Tests

If using `pytest-asyncio`:

```python
import pytest

@pytest.mark.asyncio
async def test_fetches_profile(api_client):
    profile = await api_client.fetch_profile("u_1")

    assert profile.id == "u_1"
```

For framework-agnostic async code, many teams use AnyIO:

```python
import pytest

@pytest.mark.anyio
async def test_worker_processes_message(worker, queue):
    await queue.put({"type": "recalculate", "account_id": "a_1"})

    await worker.run_one()

    assert await queue.empty()
```

Async testing rules:

- never leave background tasks running after a test;
- use fake clocks or explicit signals instead of sleeps;
- assert cancellation paths;
- test timeout behavior;
- reset event-loop global state between tests.

### Testing Exceptions

```python
import pytest

def test_rejects_negative_invoice_total():
    with pytest.raises(ValueError, match="total must be non-negative"):
        create_invoice(total_cents=-1)
```

Check exception type and message for domain errors. A test that only says "raises something" is often too weak.

### Property-Based Testing with Hypothesis

Example-based tests check cases you thought of. Property-based tests check invariants across many generated cases.

```python
from hypothesis import given, strategies as st

from billing.money import Money

@given(
    cents=st.integers(min_value=0, max_value=10_000_000),
    parts=st.integers(min_value=1, max_value=100),
)
def test_split_preserves_total(cents, parts):
    money = Money(cents)

    pieces = money.split(parts)

    assert sum(piece.cents for piece in pieces) == cents
    assert len(pieces) == parts
    assert max(piece.cents for piece in pieces) - min(piece.cents for piece in pieces) <= 1
```

Good properties:

- round trip: decode(encode(x)) == x;
- preservation: sorting preserves elements;
- monotonicity: increasing input does not decrease output;
- idempotence: normalize(normalize(x)) == normalize(x);
- commutativity: a + b == b + a where valid;
- invariant after operation sequence: balance never negative;
- equivalence: optimized implementation matches simple reference implementation.

Weak properties simply repeat the implementation logic. Strong properties describe the domain.

### Testing Flask, FastAPI, and Django

The same principles apply:

- test pure domain code without the framework;
- test API handlers through the framework's test client;
- test database behavior with real migrations;
- test permissions at both policy and route levels;
- keep a small E2E smoke suite for critical flows.

FastAPI example:

```python
def test_create_invoice_returns_201(client):
    response = client.post("/invoices", json={"customer_id": "c_1", "total_cents": 4200})

    assert response.status_code == 201
    assert response.json()["total_cents"] == 4200
```

Django example:

```python
import pytest

@pytest.mark.django_db
def test_customer_can_see_own_invoice(client, django_user_model):
    user = django_user_model.objects.create_user(username="a", password="pw")
    invoice = Invoice.objects.create(user=user, total_cents=4200)
    client.force_login(user)

    response = client.get(f"/invoices/{invoice.id}/")

    assert response.status_code == 200
```

Framework tests are valuable, but do not bury all business logic in route tests. Route tests should prove wiring, authorization, serialization, and framework behavior. Domain tests should prove business rules.

### Python Integration Tests

Use real dependencies when the dependency is part of the behavior:

- SQL migrations and queries,
- transaction behavior,
- unique constraints,
- JSON serialization,
- message publishing format,
- object storage path conventions.

For databases, prefer isolated schemas, transactions, or containers over shared developer databases.

```python
@pytest.mark.integration
def test_invoice_number_is_unique(postgres):
    repo = InvoiceRepository(postgres)
    repo.create(number="INV-001")

    with pytest.raises(DuplicateInvoiceNumber):
        repo.create(number="INV-001")
```

The point of this test is not Python. It is the contract between application code and the database.

### Python Testing Pitfalls

| Pitfall | Better approach |
|---|---|
| Patching the wrong import path | Patch where the name is looked up, or inject dependencies. |
| Overusing mocks | Use fakes for domain boundaries and real dependencies in integration tests. |
| Hidden autouse fixtures | Make important setup explicit. |
| Asserting exact log strings | Assert stable fields, event names, or structured log keys. |
| Tests depend on order | Isolate state and randomize order occasionally. |
| Sleeps in async tests | Use events, fake clocks, polling helpers, or direct synchronization. |
| Factory data too large | Use builders with small domain-relevant defaults. |
| Coverage-only mindset | Add edge, branch, property, and regression tests. |

---

## Part 6 - Node.js Testing

Node testing is really JavaScript/TypeScript testing plus the runtime details of Node: ESM vs CommonJS, async behavior, timers, event loop, process state, module mocking, browser-vs-server boundaries, and package-manager scripts.

### Recommended Node Stack

For backend services:

```text
node:test or Vitest
node:assert/strict, expect, or Chai-style matchers
c8 or built-in coverage where appropriate
fast-check for property tests
undici MockAgent, nock, MSW, or explicit fake clients for HTTP
testcontainers or Docker Compose for DB/queue integration tests
Playwright for E2E where browser behavior matters
```

For frontend/Vite apps:

```text
Vitest
Testing Library
jsdom or happy-dom for DOM-like tests
Playwright or Cypress for browser E2E/component tests
MSW for network boundaries
fast-check for pure logic and state-machine tests
```

For large legacy React/Jest estates, Jest remains common and capable. For new Node-only packages, the built-in `node:test` runner is often enough.

### Project Layout

```text
project/
  package.json
  src/
    billing/
      invoice.ts
      service.ts
  test/
    unit/
      invoice.test.ts
    integration/
      repository.test.ts
    contract/
      payments.contract.test.ts
```

Scripts:

```json
{
  "scripts": {
    "test": "node --test",
    "test:unit": "node --test test/unit/**/*.test.js",
    "test:watch": "node --test --watch",
    "test:integration": "node --test test/integration/**/*.test.js"
  }
}
```

If using TypeScript, decide whether tests run after compilation, through a runtime loader, or through Vitest/Jest transforms. In enterprise repositories, make this boring and standardized.

### `node:test`

```javascript
// src/discounts.js
export function discountRate(tier) {
  if (tier === 'enterprise') return 0.20;
  if (tier === 'pro') return 0.10;
  return 0;
}
```

```javascript
// test/unit/discounts.test.js
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { discountRate } from '../../src/discounts.js';

test('enterprise customers receive twenty percent discount', () => {
  assert.equal(discountRate('enterprise'), 0.20);
});
```

`node:test` supports `test`, `describe`/`it` aliases, hooks, subtests, concurrency controls, watch mode, reporters, mocking utilities, and timer mocking. It is especially attractive for libraries and backend code that do not need a heavy framework.

### Subtests

```javascript
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { discountRate } from '../../src/discounts.js';

describe('discountRate', () => {
  const cases = [
    ['enterprise', 0.20],
    ['pro', 0.10],
    ['free', 0],
    ['unknown', 0],
  ];

  for (const [tier, expected] of cases) {
    it(`returns ${expected} for ${tier}`, () => {
      assert.equal(discountRate(tier), expected);
    });
  }
});
```

This is Node's version of table-driven tests.

### Async Tests

```javascript
import assert from 'node:assert/strict';
import { test } from 'node:test';

test('fetches profile', async () => {
  const profile = await client.fetchProfile('u_1');

  assert.equal(profile.id, 'u_1');
});
```

Async rules:

- return or await promises;
- fail on unhandled rejections;
- avoid callbacks unless testing callback APIs;
- use `AbortController` in production code and test cancellation;
- do not use real sleeps;
- clean up servers, sockets, workers, and timers.

### Timer Mocking

Node's test context can mock timers:

```javascript
import assert from 'node:assert/strict';
import { test } from 'node:test';

test('expires token after one hour', (t) => {
  t.mock.timers.enable({ apis: ['Date', 'setTimeout'], now: 0 });

  const token = issueToken('u_1');
  t.mock.timers.tick(60 * 60 * 1000);

  assert.equal(token.isExpired(), true);
});
```

Fake timers are essential for:

- retries,
- backoff,
- TTL expiration,
- scheduled jobs,
- debounce/throttle,
- timeouts,
- token expiry.

Fake timers can also hide event-loop behavior if overused. Use them for code whose behavior is time-dependent; use real integration tests for timer APIs if the runtime behavior itself matters.

### Dependency Injection in Node

Explicit dependencies make tests simple:

```javascript
export function createBillingService({ repo, paymentGateway, clock }) {
  return {
    async pay(invoiceId) {
      const invoice = await repo.get(invoiceId);
      const result = await paymentGateway.charge({
        amountCents: invoice.totalCents,
        idempotencyKey: invoice.id,
      });

      if (result.status === 'ok') {
        await repo.markPaid(invoice.id, clock.now());
      }

      return result;
    },
  };
}
```

```javascript
import assert from 'node:assert/strict';
import { test } from 'node:test';

import { createBillingService } from '../../src/billing/service.js';

test('does not mark invoice paid when card is declined', async () => {
  const repo = new FakeInvoiceRepo([{ id: 'inv_1', totalCents: 4200 }]);
  const paymentGateway = {
    charge: async () => ({ status: 'declined', code: 'card_declined' }),
  };
  const service = createBillingService({
    repo,
    paymentGateway,
    clock: { now: () => new Date('2026-01-01T00:00:00Z') },
  });

  const result = await service.pay('inv_1');

  assert.equal(result.status, 'declined');
  assert.equal(repo.getSync('inv_1').status, 'open');
});
```

This is usually better than module mocking. Module mocking is sometimes necessary for legacy code, but dependency injection makes tests less magical.

### Jest

Jest provides a batteries-included test runner, matchers, mocking, fake timers, snapshot testing, and broad ecosystem support.

```javascript
import { discountRate } from './discounts';

test('enterprise customers receive twenty percent discount', () => {
  expect(discountRate('enterprise')).toBe(0.20);
});
```

Jest is a good fit when:

- the repo already uses Jest,
- snapshot testing is part of the workflow,
- React Native or legacy Babel-heavy setup needs Jest ecosystem support,
- rich mock APIs are important.

Jest can be heavier than needed for simple Node packages. For ESM-first projects, verify the current Jest/TypeScript/transform story before standardizing.

### Vitest

Vitest is a Vite-native test runner with Jest-compatible APIs. It is especially strong for Vite, Vue, React, Svelte, and TypeScript-heavy frontend apps.

```javascript
import { describe, expect, it } from 'vitest';

describe('discountRate', () => {
  it('returns enterprise discount', () => {
    expect(discountRate('enterprise')).toBe(0.20);
  });
});
```

Vitest is a good fit when:

- the app already uses Vite,
- fast watch mode matters,
- TypeScript/ESM/JSX transforms should match the app,
- Jest-like APIs are desired without Jest's full stack.

### Testing HTTP Servers

For Node APIs, test at multiple levels:

- pure handlers/services with fake dependencies,
- HTTP route tests with the framework test API or a real local server,
- contract tests for request/response shape,
- E2E smoke tests through real deployment.

Example using a real HTTP server:

```javascript
import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';

import { createServer } from '../../src/server.js';

let server;
let baseUrl;

before(async () => {
  server = createServer({ repo: new FakeInvoiceRepo() });
  await new Promise(resolve => server.listen(0, resolve));
  const { port } = server.address();
  baseUrl = `http://127.0.0.1:${port}`;
});

after(async () => {
  await new Promise(resolve => server.close(resolve));
});

test('POST /invoices creates invoice', async () => {
  const response = await fetch(`${baseUrl}/invoices`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ customerId: 'c_1', totalCents: 4200 }),
  });

  assert.equal(response.status, 201);
  assert.equal((await response.json()).totalCents, 4200);
});
```

Use random ports (`listen(0)`) to avoid port collisions. Always close servers.

### Browser and UI Tests

Use DOM/component tests for component behavior and browser E2E tests for critical flows.

Good UI tests assert user-visible behavior:

```javascript
await page.getByRole('button', { name: 'Pay invoice' }).click();
await expect(page.getByText('Payment complete')).toBeVisible();
```

Weak UI tests assert implementation:

```javascript
expect(component.state().paid).toBe(true);
expect(wrapper.find('.btn-primary').length).toBe(1);
```

Modern Playwright and Cypress tests should prefer accessible locators:

- role,
- label,
- text,
- placeholder,
- alt text,
- test IDs only where user-facing locators are unstable or ambiguous.

Browser E2E rules:

- keep the suite small;
- seed state through APIs, not UI setup flows;
- avoid sharing accounts across tests;
- collect trace/video/screenshot on failure;
- run cross-browser only for flows where browser differences matter;
- isolate tests enough for parallel execution.

### Property-Based Testing with fast-check

```javascript
import assert from 'node:assert/strict';
import { test } from 'node:test';
import fc from 'fast-check';

import { splitMoney } from '../../src/money.js';

test('splitMoney preserves total', () => {
  fc.assert(
    fc.property(
      fc.integer({ min: 0, max: 10_000_000 }),
      fc.integer({ min: 1, max: 100 }),
      (cents, parts) => {
        const pieces = splitMoney(cents, parts);
        assert.equal(pieces.reduce((sum, piece) => sum + piece, 0), cents);
        assert.equal(pieces.length, parts);
        assert.ok(Math.max(...pieces) - Math.min(...pieces) <= 1);
      },
    ),
  );
});
```

fast-check works with major test runners. Use it for parsers, serializers, validators, reducers, state machines, permission rules, date/time calculations, and domain invariants.

### Node Testing Pitfalls

| Pitfall | Better approach |
|---|---|
| Forgetting to await promises | Return/await every async operation; fail on unhandled rejections. |
| Leaving servers open | Use hooks and cleanup; close servers, sockets, workers, timers. |
| Testing implementation details in React | Use Testing Library and accessible queries. |
| Massive snapshots | Prefer semantic assertions; review snapshot diffs carefully. |
| Module mocking ESM pain | Prefer explicit dependency injection where possible. |
| Shared global process state | Isolate env vars, cwd, timers, module caches, and random seeds. |
| Real sleeps | Use fake timers, polling assertions, or explicit synchronization. |
| Browser tests doing all setup via UI | Seed data through API/database fixtures. |

---

## Part 7 - Go Testing

Go's testing story is intentionally simple. The standard `testing` package covers unit tests, subtests, benchmarks, examples, fuzz tests, cleanup, temporary directories, and parallel execution. Add the race detector, `httptest`, and table-driven tests, and you have a surprisingly complete stack.

### Recommended Go Stack

```text
testing package
go test ./...
table-driven tests
subtests with t.Run
httptest for HTTP handlers/clients
go test -race for concurrency
go test -fuzz for fuzzing
benchmarks with go test -bench
testcontainers-go or Docker Compose for integration dependencies
```

Popular assertion libraries exist (`testify`, `go-cmp`, `require`, etc.), but Go's standard approach is explicit checks. In large teams, consistency matters more than purism.

### Project Layout

Go keeps tests beside code:

```text
billing/
  invoice.go
  invoice_test.go
  repository.go
  repository_integration_test.go
```

Tests live in files ending `_test.go`.

Two package styles:

```go
package billing
```

This can test unexported identifiers. Use it for close unit tests.

```go
package billing_test
```

This imports the package as an external consumer. Use it to test public API behavior.

### Basic Go Test

```go
// invoice.go
package billing

func DiscountRate(tier string) float64 {
	switch tier {
	case "enterprise":
		return 0.20
	case "pro":
		return 0.10
	default:
		return 0
	}
}
```

```go
// invoice_test.go
package billing

import "testing"

func TestDiscountRateEnterprise(t *testing.T) {
	got := DiscountRate("enterprise")
	want := 0.20

	if got != want {
		t.Fatalf("DiscountRate(\"enterprise\") = %v, want %v", got, want)
	}
}
```

Run:

```bash
go test ./...
go test -v ./...
go test ./billing -run TestDiscountRateEnterprise
```

### Table-Driven Tests

Go's idiom:

```go
func TestDiscountRate(t *testing.T) {
	tests := []struct {
		name string
		tier string
		want float64
	}{
		{name: "enterprise", tier: "enterprise", want: 0.20},
		{name: "pro", tier: "pro", want: 0.10},
		{name: "free", tier: "free", want: 0},
		{name: "unknown", tier: "unknown", want: 0},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := DiscountRate(tt.tier)
			if got != tt.want {
				t.Fatalf("DiscountRate(%q) = %v, want %v", tt.tier, got, tt.want)
			}
		})
	}
}
```

Table-driven tests are excellent when:

- inputs and expected outputs are clear;
- all cases test the same behavior;
- names are descriptive;
- the table is not hiding complex setup.

### `t.Helper`

```go
func requireNoError(t *testing.T, err error) {
	t.Helper()
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}
```

Call `t.Helper()` in test helpers so failure lines point to the test, not the helper.

### `t.Cleanup` and `t.TempDir`

```go
func TestWritesInvoiceFile(t *testing.T) {
	dir := t.TempDir()
	repo := NewFileInvoiceRepository(dir)

	if err := repo.Save("inv_1", []byte("invoice")); err != nil {
		t.Fatalf("save invoice: %v", err)
	}
}
```

`t.TempDir()` creates a temporary directory and removes it after the test. `t.Cleanup()` registers cleanup functions:

```go
func startTestServer(t *testing.T) *Server {
	t.Helper()

	srv := NewServer()
	go srv.Start()
	t.Cleanup(func() {
		_ = srv.Stop()
	})

	return srv
}
```

### Parallel Tests

```go
func TestDiscountRate(t *testing.T) {
	tests := []struct {
		name string
		tier string
		want float64
	}{
		{name: "enterprise", tier: "enterprise", want: 0.20},
		{name: "pro", tier: "pro", want: 0.10},
	}

	for _, tt := range tests {
		tt := tt
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			if got := DiscountRate(tt.tier); got != tt.want {
				t.Fatalf("got %v, want %v", got, tt.want)
			}
		})
	}
}
```

Rules for `t.Parallel()`:

- avoid shared mutable state;
- avoid fixed ports;
- avoid shared temp paths;
- be careful with environment variables;
- capture loop variables correctly in older Go code patterns.

### Testing HTTP Handlers

```go
func TestCreateInvoice(t *testing.T) {
	repo := NewFakeInvoiceRepo()
	handler := NewHandler(repo)

	req := httptest.NewRequest(http.MethodPost, "/invoices",
		strings.NewReader(`{"customer_id":"c_1","total_cents":4200}`))
	req.Header.Set("content-type", "application/json")
	rec := httptest.NewRecorder()

	handler.ServeHTTP(rec, req)

	if rec.Code != http.StatusCreated {
		t.Fatalf("status = %d, want %d; body=%s", rec.Code, http.StatusCreated, rec.Body.String())
	}
}
```

`httptest` is one of Go's best testing tools. Use it for handlers, middleware, clients, and local servers.

### Interfaces and Fakes

Go does not need a mocking framework for many cases. Define small interfaces at the consumer side:

```go
type PaymentGateway interface {
	Charge(ctx context.Context, req ChargeRequest) (ChargeResult, error)
}
```

Fake:

```go
type fakePaymentGateway struct {
	result ChargeResult
	err    error
	calls  []ChargeRequest
}

func (f *fakePaymentGateway) Charge(ctx context.Context, req ChargeRequest) (ChargeResult, error) {
	f.calls = append(f.calls, req)
	return f.result, f.err
}
```

Test:

```go
func TestDeclinedPaymentDoesNotMarkInvoicePaid(t *testing.T) {
	repo := NewFakeInvoiceRepo()
	gateway := &fakePaymentGateway{
		result: ChargeResult{Status: "declined", Code: "card_declined"},
	}
	service := NewBillingService(repo, gateway)

	result, err := service.Pay(context.Background(), "inv_1")
	if err != nil {
		t.Fatalf("Pay: %v", err)
	}
	if result.Status != "declined" {
		t.Fatalf("status = %q, want declined", result.Status)
	}
	if got := repo.Get("inv_1").Status; got != "open" {
		t.Fatalf("invoice status = %q, want open", got)
	}
}
```

Keep interfaces small. In Go, huge interfaces are hard to fake and often reveal misplaced abstractions.

### Golden Files

Golden files store expected output:

```go
func TestRenderInvoice(t *testing.T) {
	got := RenderInvoice(sampleInvoice())
	wantPath := filepath.Join("testdata", "invoice.golden")

	if *update {
		if err := os.WriteFile(wantPath, got, 0o644); err != nil {
			t.Fatalf("update golden: %v", err)
		}
	}

	want, err := os.ReadFile(wantPath)
	if err != nil {
		t.Fatalf("read golden: %v", err)
	}
	if diff := cmp.Diff(string(want), string(got)); diff != "" {
		t.Fatalf("rendered invoice mismatch (-want +got):\n%s", diff)
	}
}
```

Golden files are good for generated SQL, JSON, code, Markdown, templates, and documents. They are bad when reviewers do not inspect diffs.

### Benchmarks

```go
func BenchmarkRenderInvoice(b *testing.B) {
	invoice := sampleInvoice()

	for b.Loop() {
		_ = RenderInvoice(invoice)
	}
}
```

Run:

```bash
go test -bench=. -benchmem ./...
```

Benchmark rules:

- use realistic input sizes;
- avoid measuring setup;
- report allocations with `-benchmem`;
- compare changes with `benchstat`;
- keep performance assertions out of regular unit tests unless they are very stable.

### Fuzzing

Go has built-in fuzzing through `testing.F`.

```go
func FuzzParseInvoiceID(f *testing.F) {
	f.Add("inv_123")
	f.Add("INV-001")
	f.Add("")

	f.Fuzz(func(t *testing.T, input string) {
		id, err := ParseInvoiceID(input)
		if err != nil {
			return
		}
		if id.String() == "" {
			t.Fatalf("parsed valid ID has empty string representation")
		}
		if _, err := ParseInvoiceID(id.String()); err != nil {
			t.Fatalf("round trip parse failed: %v", err)
		}
	})
}
```

Run seed corpus as normal tests:

```bash
go test ./...
```

Run fuzzing:

```bash
go test -fuzz=FuzzParseInvoiceID ./billing
```

Good fuzz targets are:

- fast,
- deterministic,
- side-effect-free,
- focused on parsers, encoders, decoders, validators, protocol handlers, compression, crypto wrappers, and security-sensitive input handling.

### Race Detector

Run:

```bash
go test -race ./...
```

The race detector finds data races that actually execute during the run. It cannot find races in untested paths, so combine it with good coverage and realistic concurrent tests.

Concurrency test example:

```go
func TestCounterConcurrent(t *testing.T) {
	var counter Counter
	var wg sync.WaitGroup

	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			counter.Inc()
		}()
	}
	wg.Wait()

	if got := counter.Value(); got != 100 {
		t.Fatalf("counter = %d, want 100", got)
	}
}
```

This test is more valuable under `-race` than by itself.

### Go Integration Tests

Use build tags or naming conventions for slow integration tests:

```go
//go:build integration

package billing

func TestPostgresInvoiceRepository(t *testing.T) {
	// real Postgres container or test database
}
```

Run:

```bash
go test ./...
go test -tags=integration ./...
```

Use real Postgres when testing SQL semantics. Use fakes when testing domain logic that happens to persist something.

### Go Testing Pitfalls

| Pitfall | Better approach |
|---|---|
| Huge interfaces | Define small consumer-side interfaces. |
| Ignoring errors in tests | Fail immediately with context. |
| Test helpers without `t.Helper()` | Mark helpers so failure lines are useful. |
| Fixed ports | Use `httptest` or `listen(0)`. |
| Shared global state with `t.Parallel()` | Isolate state or avoid parallelizing those tests. |
| Only happy-path table rows | Include edge cases and invalid inputs. |
| Benchmarks include setup | Move setup outside timed loop. |
| Race detector only in rare manual runs | Add scheduled or PR-targeted `go test -race`. |

---

## Part 8 - Methodologies and Specialized Testing

Methodology is useful when it changes how you think, not when it becomes ceremony.

### Test-Driven Development

TDD loop:

```text
red -> green -> refactor
```

1. Write a failing test for the behavior you want.
2. Write the simplest production code that passes.
3. Refactor while keeping tests green.

TDD is strongest when:

- requirements can be expressed as examples;
- code has clear inputs and outputs;
- design pressure is valuable;
- the team is working in small increments.

TDD is weaker when:

- exploring unknown APIs,
- building visual designs,
- reverse-engineering legacy behavior,
- testing requires expensive infrastructure.

Even if you do not practice strict TDD, the TDD instinct is useful: before changing code, ask "how will I know this works?"

### Behavior-Driven Development

BDD tries to align product, engineering, and QA around examples:

```gherkin
Feature: Invoice payment

  Scenario: Card is declined
    Given an unpaid invoice for $42.00
    When the customer pays with a declined card
    Then the invoice remains unpaid
    And the customer sees "Card declined"
```

BDD works when scenarios are a collaboration tool. It fails when Gherkin becomes a second programming language maintained by people far from the code.

Use BDD for:

- critical business workflows,
- regulated acceptance criteria,
- cross-functional communication,
- product-readable examples.

Keep step definitions thin. Put business logic in application code, not in the test DSL.

### Acceptance Test-Driven Development

ATDD defines acceptance tests before implementation. It is similar to BDD but less tied to syntax.

The key move:

```text
Before building:
  "What examples would convince us this story is done?"
```

Great acceptance criteria include:

- happy path,
- authorization,
- validation failures,
- idempotency/retry behavior,
- audit/event side effects,
- observability expectations,
- backward compatibility.

### Specification by Example

Specification by example treats examples as the living spec. This is excellent for domains like pricing, eligibility, tax, billing, permissions, and compliance.

Example table:

| Customer | Region | Invoice age | Expected action |
|---|---|---:|---|
| enterprise | US | 10 days | no reminder |
| pro | US | 31 days | send reminder |
| free | EU | 31 days | send reminder with EU template |
| enterprise | EU | 61 days | notify account manager |

Turn the table into tests, but keep the table understandable to domain experts.

### Property-Based Testing

Property-based testing asks: "What must always be true?"

Use it when:

- input space is large;
- edge cases are easy to miss;
- there is a clear invariant;
- a reference implementation exists;
- shrinking failures to minimal examples is valuable.

Great targets:

- parsers,
- serializers,
- validators,
- date/time logic,
- money splitting,
- permissions,
- state machines,
- search/filter/sort,
- compression,
- protocol handling.

Bad targets:

- code with weak oracles,
- code with heavy side effects,
- code where generated inputs are mostly invalid and uninteresting,
- behavior whose "correctness" is a UX judgment.

### Fuzz Testing

Fuzzing is especially useful for:

- untrusted input,
- parsers,
- network protocols,
- file formats,
- security-sensitive code,
- native extensions,
- crash/hang detection.

Property testing often starts from a semantic invariant. Fuzzing often starts from "do not crash, hang, leak, corrupt, or accept invalid structure." The overlap is real; the emphasis differs.

### Mutation Testing

Mutation testing changes production code and checks whether tests fail.

Example mutations:

- `>` becomes `>=`,
- `&&` becomes `||`,
- return value changes,
- branch removed,
- exception swallowed.

If tests still pass, the mutant survived. That suggests weak assertions or missing cases.

Use mutation testing for:

- core libraries,
- safety-critical logic,
- permission systems,
- pricing/billing,
- shared packages.

Do not run mutation testing on every PR unless your tooling is fast and scoped. It is usually a scheduled or targeted quality tool.

### Contract Testing

Contract testing solves this microservice problem:

```text
Provider changed safely according to its tests.
Consumer broke because it depended on a behavior the provider did not know about.
```

Contract tests make the dependency explicit.

Contract types:

- API contracts: OpenAPI, JSON schema, protobuf, gRPC;
- consumer-driven contracts: Pact-style examples from consumers;
- event contracts: schema and semantics of emitted events;
- database contracts: migration compatibility for shared DBs, ideally avoided;
- UI contracts: design-system component behavior.

Contract testing is not a replacement for integration testing. It is a way to catch compatibility problems earlier and with clearer ownership.

### Performance Testing

Performance tests answer different questions:

| Test | Question |
|---|---|
| Microbenchmark | Did this function get slower or allocate more? |
| Load test | Can the service handle expected traffic? |
| Stress test | Where does it break? |
| Soak test | Does it degrade over hours or days? |
| Spike test | What happens during sudden bursts? |
| Capacity test | How much hardware do we need? |

Performance testing rules:

- define workload before tooling;
- use production-like data size;
- measure percentiles, not only averages;
- include dependency latency and error rates;
- separate client bottlenecks from server bottlenecks;
- track regressions over time;
- combine with profiling and observability.

### Security Testing

Security testing is not a single scanner. It includes:

- threat modeling,
- secure code review,
- dependency scanning,
- SAST,
- DAST,
- IAST/RASP where appropriate,
- fuzzing,
- abuse-case tests,
- authentication and authorization tests,
- secrets scanning,
- infrastructure policy checks,
- penetration testing.

OWASP's testing guidance is useful because it treats security testing as a lifecycle activity, not a final gate. For web apps, at minimum, test:

- authentication,
- authorization,
- session management,
- input validation,
- output encoding,
- CSRF where relevant,
- SSRF,
- file upload,
- security headers,
- rate limiting,
- audit logging,
- tenant isolation.

Authorization deserves special emphasis. Most teams under-test it. Write explicit tests for:

- same-tenant access allowed,
- cross-tenant access denied,
- lower role denied,
- deleted/suspended user denied,
- service account scope enforced,
- object-level permissions enforced.

### Accessibility Testing

Accessibility testing combines automation and human judgment.

Automated checks can catch:

- missing labels,
- color contrast failures,
- invalid ARIA,
- keyboard traps in some cases,
- heading/order issues.

Human/manual checks are still needed for:

- keyboard-only workflow quality,
- screen reader usability,
- focus order,
- meaning and context,
- cognitive load.

Make accessibility part of component tests and E2E smoke checks. Do not wait until a legal or customer escalation.

### Exploratory Testing

Exploratory testing is skilled investigation. It is not "click around randomly."

Good exploratory charters:

- "Try to break invoice editing with concurrent sessions."
- "Explore permissions around delegated billing admins."
- "Look for confusing states during partial payment failure."
- "Test checkout with slow network and duplicate clicks."

Exploratory findings should become:

- bug reports,
- regression tests,
- improved acceptance criteria,
- observability gaps,
- UX changes.

---

## Part 9 - Distributed and Non-Deterministic Systems

Modern systems are full of behavior that is hard to test with simple examples: retries, queues, eventual consistency, idempotency, background jobs, caches, distributed locks, streaming, and AI/LLM outputs. The trick is to test invariants and control sources of nondeterminism.

### Eventual Consistency

Bad test:

```javascript
await publishEvent(event)
expect(await readProjection()).toEqual(expected)
```

This races the projection.

Better:

```javascript
await publishEvent(event)
await expectEventually(async () => {
  const projection = await readProjection()
  assert.deepEqual(projection, expected)
})
```

But polling is only half the answer. Also test:

- duplicate event handling,
- out-of-order events if possible,
- missing dependency behavior,
- replay from start,
- idempotency keys,
- dead-letter behavior,
- observability when processing fails.

### Idempotency

For distributed systems, idempotency is a testing superpower.

Property:

```text
Applying the same command twice has the same externally visible result as applying it once.
```

Test examples:

- duplicate payment callback does not double-charge;
- retrying create with same idempotency key returns same resource;
- event consumer can process duplicate events safely;
- migration can run twice without corruption;
- scheduled job can resume after partial failure.

### Retries and Backoff

Test retry behavior with fake dependencies and fake clocks.

Scenarios:

- transient error succeeds on retry;
- permanent error does not retry;
- max attempts honored;
- retry delay increases;
- jitter stays within bounds;
- cancellation stops retries;
- idempotency key is reused across attempts;
- retry logs/metrics include attempt count.

Avoid tests that wait real seconds. They are slow and flaky.

### Message Queues

Queue tests should cover:

- serialization shape,
- routing key/topic,
- acknowledgement behavior,
- retry/dead-letter policy,
- poison messages,
- idempotent consumers,
- visibility timeout/lease extension,
- ordering assumptions,
- backpressure.

Use unit tests for handler logic, integration tests for broker semantics, and E2E smoke tests for wiring.

### Caches

Cache bugs are often consistency bugs.

Test:

- miss loads and stores;
- hit avoids dependency call where that matters;
- TTL expires;
- invalidation removes stale data;
- negative caching behavior;
- stampede protection;
- cache key includes tenant/user/locale/permission dimensions;
- stale data does not violate security or correctness.

If stale data is acceptable, write that into the test oracle. Ambiguous cache behavior becomes production folklore.

### Concurrency

Concurrency tests are hard because bugs are schedule-dependent.

Use:

- race detectors where available;
- stress loops;
- deterministic schedulers if the ecosystem provides one;
- property tests over operation sequences;
- clear invariants;
- small critical sections;
- production telemetry for contention and deadlocks.

In Go, run `go test -race`. In Python, test thread/process boundaries with explicit synchronization. In Node, test worker threads and async concurrency with controlled promises and abort signals.

### Testing LLM and AI Features

AI systems add nondeterministic outputs and fuzzy correctness. Do not test them like pure functions unless the model call is stubbed.

Use layers:

1. Unit test prompt assembly and tool schemas deterministically.
2. Unit test parsers and validators for model output.
3. Contract test tool calls and permission boundaries.
4. Evaluation test model behavior over curated examples.
5. Regression test known failure cases.
6. Production monitor quality, cost, latency, refusal/error rate, and human feedback.

Good assertions for LLM features:

- output parses into required schema;
- citations point to supplied documents;
- no tool call outside allowlist;
- no PII in logs;
- refusal happens for prohibited request class;
- answer satisfies rubric above threshold;
- cost and latency stay within budget.

Weak assertions:

- exact wording from a model,
- snapshot of a generated paragraph,
- single golden response for a broad task.

LLM tests need versioned eval sets and human review loops. A model upgrade is a behavioral dependency change.

---

## Part 10 - Enterprise Testing Strategy

Enterprise testing is not "more tests." It is aligning quality signals across people, architecture, pipelines, compliance, and production operations.

### The Enterprise Goal

A good enterprise testing strategy lets the organization answer:

- Can developers change code quickly and safely?
- Which tests block merges, releases, or deployments?
- Who owns each failing signal?
- How do we know a service is compatible with its consumers?
- How are security, privacy, and compliance requirements verified?
- How are flaky tests handled?
- How is test data created, protected, and cleaned?
- How does production monitoring feed back into tests?
- How do teams improve the portfolio over time?

The strategy must be written down, but it should be short enough that engineers actually read it.

### Quality Ownership

The strongest enterprise model:

```text
Teams own the quality of the code and services they ship.
Specialists build expertise, platforms, tools, and coaching.
Pipelines enforce shared minimum standards.
Production telemetry validates real behavior.
```

QA should not be a late-stage department that receives finished work and discovers preventable problems. QA expertise is valuable, but it should move upstream into:

- acceptance criteria,
- exploratory testing,
- test design,
- risk analysis,
- automation strategy,
- release readiness,
- coaching engineers,
- quality metrics.

### Shift Left and Shift Right

Shift left:

- involve testing during requirements and design;
- write unit/integration tests before merge;
- run security and static checks early;
- make testability part of architecture review;
- catch defects before they become release surprises.

Shift right:

- use canaries,
- feature flags,
- synthetic monitoring,
- SLOs,
- production telemetry,
- real-user monitoring,
- incident review,
- safe rollback.

Mature teams do both. Pre-production tests reduce risk; production signals reveal reality.

### Test Strategy Document

A useful test strategy includes:

```text
1. Scope
   What systems, teams, and risks are covered?

2. Quality goals
   What does "good enough to release" mean?

3. Test levels
   What test types exist and where do they run?

4. Ownership
   Who owns failures, fixtures, environments, contracts, and test data?

5. Tooling standards
   Approved frameworks, naming, layout, reports, coverage, flake process.

6. CI/CD gates
   Which checks block PR, merge, release, deployment?

7. Environment strategy
   Local, ephemeral, shared staging, pre-prod, production checks.

8. Data strategy
   Synthetic data, anonymized production data, fixtures, cleanup, privacy.

9. Non-functional testing
   Security, performance, accessibility, resilience, compliance.

10. Metrics and improvement
   Lead time, failure rate, flake rate, escaped defects, MTTR, coverage trends.
```

If a document cannot answer what happens when a critical test flakes on release day, it is incomplete.

### Enterprise Test Levels

Many large organizations use levels similar to:

| Level | Example | Purpose | Gate |
|---|---|---|---|
| L0 | static checks, unit tests | immediate developer feedback | PR |
| L1 | integration with local dependencies | component confidence | PR or merge |
| L2 | service/component tests in ephemeral env | deployable confidence | merge/release |
| L3 | cross-service E2E critical flows | business journey confidence | release |
| L4 | performance/security/resilience | specialized risk confidence | scheduled/release |
| Prod | canaries, synthetics, SLOs | real-world confidence | deployment/operation |

The exact names do not matter. The separation does.

### Architecture for Testability

Enterprise testing starts in architecture.

Design for:

- explicit dependencies,
- small domain cores,
- stable public interfaces,
- idempotent operations,
- deterministic clocks/IDs/randomness,
- observable state transitions,
- tenant-aware test data,
- local runnable services,
- health endpoints,
- admin/test-only APIs where safe,
- contract-first APIs,
- feature flags with test hooks,
- backwards-compatible migrations.

If a system cannot be tested without a full shared environment and three manual setup steps, the architecture is taxing every future change.

### Test Data Management

Test data is an enterprise problem.

Principles:

- prefer synthetic data;
- never depend on one shared mutable "magic account";
- isolate by test run, tenant, namespace, or transaction;
- clean up automatically;
- avoid production PII in lower environments;
- version fixtures with schema changes;
- make data builders domain-aware;
- keep seed data minimal;
- test migrations on realistic data volume.

Patterns:

| Pattern | Use when | Watch out |
|---|---|---|
| Transaction rollback | DB integration tests | async/background work outside transaction |
| Per-test schema/database | parallel DB tests | setup time |
| Containers | local parity | startup cost |
| Synthetic fixture service | many teams need consistent data | central bottleneck |
| Anonymized production snapshot | performance/migration realism | privacy, staleness, size |
| API seeding | E2E setup | slow if overused |

### Environment Strategy

Environments form a ladder:

```text
local -> CI ephemeral -> shared integration -> staging/pre-prod -> production
```

Local:

- fast,
- developer-owned,
- minimal dependencies,
- works offline where possible.

CI ephemeral:

- created per PR/job,
- isolated,
- reproducible,
- destroyed automatically.

Shared integration:

- useful for cross-team testing,
- dangerous if it becomes the only place tests pass.

Staging/pre-prod:

- production-like,
- used for release rehearsal,
- not a dumping ground for flaky tests.

Production:

- canaries,
- synthetics,
- SLOs,
- feature flags,
- rollback.

The higher the environment, the fewer tests should be required to get signal.

### Flaky Test Management

A flaky test is a test that sometimes passes and sometimes fails without a relevant code change. It is organizationally expensive because it trains people to distrust the suite.

Flake policy:

1. Detect and label flaky failures.
2. Assign an owner immediately.
3. Quarantine only if necessary, with an expiry.
4. Keep quarantined tests visible.
5. Fix root cause.
6. Track flake rate as a quality metric.

Common flake causes:

- real time sleeps,
- shared state,
- fixed ports,
- test order dependency,
- async work not awaited,
- eventually consistent assertions without polling,
- external service dependency,
- resource contention,
- random data without seed logging,
- browser selector instability.

Never solve flakiness only by rerunning. Reruns are a diagnostic and mitigation tool, not a cure.

### Metrics That Help

Useful:

- PR feedback time,
- test failure rate by suite,
- flaky test rate,
- quarantine age,
- escaped defect rate by category,
- mean time to diagnose failures,
- coverage trend for critical packages,
- mutation score for critical libraries,
- E2E pass rate by journey,
- deployment rollback rate,
- production SLO burn related to defects.

Dangerous:

- individual developer coverage score,
- raw number of tests as success,
- 100 percent coverage mandate,
- pass rate without flake tracking,
- bugs found by QA as a team performance contest.

Metrics should improve decisions, not create games.

### Compliance and Regulated Environments

Regulated teams may need evidence:

- requirement-to-test traceability,
- approvals,
- signed test reports,
- audit logs,
- change records,
- validation of tools,
- segregation of duties,
- data retention.

Do not treat compliance as separate from engineering. The best approach is to generate evidence from the normal delivery pipeline:

- test reports attached to builds,
- artifact provenance,
- code review records,
- deployment approvals,
- automated control checks,
- immutable logs.

Manual evidence collection is expensive and error-prone.

---

## Part 11 - CI/CD, Test Selection, and Feedback Loops

The CI pipeline is a product. Engineers are its users. Its job is to deliver trustworthy feedback quickly.

### A Practical Pipeline

```text
Local pre-commit:
  format, lint staged files, focused unit tests

PR fast gate:
  format, lint, type/static checks, unit tests, selected integration tests

PR extended gate:
  contract tests, DB migration tests, component tests, selected E2E smoke

Main branch:
  full integration, full contract, full component, broader E2E

Nightly/scheduled:
  fuzz, mutation, long performance, security scans, race/stress, full browser matrix

Pre-prod/release:
  deployment smoke, migration rehearsal, critical journeys

Production:
  canary, synthetic checks, SLOs, real-user monitoring, rollback triggers
```

Not every repo needs every stage. But every repo needs an intentional feedback ladder.

### Keep PR Feedback Fast

Targets vary, but a healthy default:

- formatting/static/unit feedback in under 5 minutes;
- PR gate in under 10-15 minutes;
- slow suites outside the critical path unless risk requires them;
- failures easy to reproduce locally.

Tactics:

- split tests by cost and purpose;
- parallelize safely;
- cache dependencies;
- reuse build artifacts;
- select tests based on changed paths;
- move broad E2E to smoke subset;
- quarantine flakes with owners;
- optimize test setup, not only test bodies;
- run integration dependencies as local containers;
- avoid shared mutable environments in PR gates.

### Test Selection

Large repositories eventually need selective testing:

- path-based selection,
- dependency graph selection,
- test impact analysis,
- tags/markers,
- historical duration balancing,
- changed package plus reverse dependencies,
- risk-based manual override.

Selection must be conservative. A missed failing test is worse than a few extra minutes.

### Reports

CI should publish:

- test results with file/test names,
- failure logs,
- screenshots/traces/videos for browser tests,
- coverage reports,
- benchmark deltas where relevant,
- flaky test annotations,
- artifacts needed for reproduction.

A failure that requires SSHing into a runner or reading 10,000 log lines is a pipeline bug.

### Merge Gates

Common gates:

- formatting,
- lint,
- type checking,
- unit tests,
- security/dependency policy,
- coverage delta for critical packages,
- integration/contract tests for changed components,
- required code review,
- generated artifact freshness,
- migration safety checks.

Avoid gates that are:

- flaky,
- unactionable,
- owned by nobody,
- too slow for the risk they cover,
- impossible to reproduce.

### Release Gates

Release gates should answer release questions:

- Did migrations run in rehearsal?
- Are critical journeys passing?
- Are provider/consumer contracts compatible?
- Did performance regress beyond budget?
- Are security scans clean or risk-accepted?
- Is rollback tested?
- Are feature flags configured?
- Are dashboards and alerts ready?

Do not use release gates to discover basic unit failures. That feedback belongs earlier.

---

## Part 12 - Legacy Systems

Legacy code often lacks tests because it is hard to test. It is hard to test because it was designed without feedback loops. The way out is incremental.

### Characterization Tests

Before changing legacy behavior, capture what it currently does:

```text
Given this ugly real input,
the legacy system returns this exact output.
```

Characterization tests are not moral endorsements. They are guardrails while you refactor.

Use them for:

- undocumented transformations,
- old pricing rules,
- batch jobs,
- report generation,
- migration scripts,
- brittle integrations.

### The Seam Strategy

A seam is a place where behavior can be changed or observed without editing the whole system.

Common seams:

- function parameters,
- interfaces,
- environment/config,
- database boundaries,
- HTTP clients,
- filesystem paths,
- command handlers,
- message handlers,
- adapters around legacy APIs.

The workflow:

1. Add characterization tests around current behavior.
2. Identify a seam.
3. Extract pure logic or adapter boundary.
4. Add focused tests.
5. Refactor behind the tests.
6. Add regression tests for fixed bugs.

### Approval Tests

For messy legacy outputs, approval tests can help:

- render report,
- serialize output,
- compare to approved golden file,
- review intentional changes.

They work well when the output is stable and reviewable. They fail when the output includes timestamps, random IDs, nondeterministic ordering, or huge irrelevant sections. Normalize those before comparing.

### Testing Around a Database-Centric Legacy App

If business logic lives in stored procedures or database triggers:

- test against a real database;
- version schema and fixtures;
- isolate transactions;
- test migrations up and down where possible;
- capture query plans for performance-critical paths;
- add application-level tests around new code as you extract logic.

Do not mock the database for behavior that is actually implemented in the database.

### The First Tests to Add

If a legacy system has almost no tests, start with:

1. Smoke test: app starts and health endpoint works.
2. Golden path E2E: most important business journey.
3. Bug regression tests: every production bug gets a test.
4. Characterization tests around risky modules.
5. Integration tests for database migrations.
6. Unit tests for newly extracted pure logic.
7. Contract tests for external APIs.

The first goal is not elegance. It is a foothold.

---

## Part 13 - Recipes and Checklists

This section is the field kit.

### Recipe: Testing a New Backend Feature

1. Clarify acceptance examples with product/QA.
2. Write unit tests for pure rules.
3. Write integration tests for database/query behavior.
4. Write API/component tests for request/response, auth, validation, and side effects.
5. Add or update contract tests if external consumers/providers are affected.
6. Add E2E coverage only if the user journey risk is not covered lower.
7. Add observability assertions where useful: emitted event, metric, audit log.
8. Add security tests for permissions and tenant boundaries.
9. Run locally, then in CI.
10. Document any intentional test gaps.

### Recipe: Testing a Bug Fix

1. Reproduce the bug manually or with a failing test.
2. Put the regression test at the lowest level that catches the bug.
3. Make the test fail for the right reason.
4. Fix the bug.
5. Confirm the test fails before the fix and passes after.
6. Consider nearby edge cases.
7. If production missed it, ask what signal was absent: test, alert, log, metric, contract, or review.

### Recipe: Testing a Third-Party API Integration

Use layers:

1. Unit tests with fake client for your business logic.
2. Contract tests against recorded/schema examples.
3. Sandbox tests against the provider if available.
4. Production-safe smoke checks for credentials and reachability.

Test:

- success,
- validation error,
- auth failure,
- rate limit,
- transient 5xx,
- timeout,
- malformed response,
- idempotency,
- pagination,
- webhook signature verification.

Do not make every unit test hit the third-party API. That is slow, flaky, and potentially expensive.

### Recipe: Testing Database Migrations

1. Start from previous schema.
2. Load representative data.
3. Apply migration.
4. Verify schema and data transformation.
5. Verify app can read/write after migration.
6. Test rollback if supported.
7. Test on realistic volume for risky migrations.
8. Include locks/timeouts in rehearsal for large tables.

Migration tests catch some of the most expensive production failures.

### Recipe: Flaky Test Triage

Ask:

- Does it depend on wall-clock time?
- Does it depend on test order?
- Does it share data with other tests?
- Does it use fixed ports/files/accounts?
- Does it leave async work running?
- Does it rely on eventual consistency without waiting?
- Does it depend on external service uptime?
- Does random data hide the seed?
- Does CI have different CPU/memory/timezone/locale?
- Does browser automation use brittle selectors?

Fix:

- isolate state,
- inject clocks,
- use deterministic seeds,
- wait for observable conditions,
- close resources,
- use random ports,
- remove external dependencies from PR gate,
- improve diagnostics.

### Recipe: Testing Authorization

For each protected action, test:

| Scenario | Expected |
|---|---|
| unauthenticated | denied |
| authenticated but wrong tenant | denied |
| correct tenant, insufficient role | denied |
| correct role, wrong object ownership | denied |
| suspended/deleted user | denied |
| service account missing scope | denied |
| valid actor | allowed |

Authorization should be tested at two levels:

- policy unit tests for decision logic;
- route/API integration tests to prove enforcement is wired.

### Decision Tree: What Test Should I Write?

```text
Can the behavior be tested as a pure function?
  yes -> unit test, maybe property test
  no ->
    Is the risk about DB/query/migration semantics?
      yes -> integration test with real DB
      no ->
        Is the risk about a service/API boundary?
          yes -> contract or component test
          no ->
            Is the risk about user-visible workflow across components?
              yes -> E2E or acceptance test
              no ->
                Is the risk non-functional?
                  yes -> performance/security/accessibility/resilience test
                  no -> reconsider the requirement and oracle
```

### PR Testing Checklist

- Tests fail before the fix when practical.
- New behavior has unit or integration coverage.
- Edge cases and error paths are covered.
- Permissions/tenant boundaries are covered.
- No real sleeps were added.
- No external service is required for unit tests.
- Test data is isolated.
- Failure messages are diagnostic.
- Coverage drop is understood.
- Flaky or slow tests are marked and justified.
- CI command is documented or standard.

### Enterprise Readiness Checklist

- Every service has a documented test strategy.
- PR feedback is fast enough that developers wait for it.
- Test ownership is clear.
- Flaky tests are tracked and fixed.
- Integration dependencies are reproducible.
- Contract tests protect important service boundaries.
- Critical journeys have E2E or synthetic coverage.
- Security tests cover authn/authz and top abuse cases.
- Performance budgets exist for critical paths.
- Test data avoids production PII.
- CI reports are actionable.
- Production incidents feed regression tests and monitoring improvements.

### Language Comparison

| Concern | Python | Node.js | Go |
|---|---|---|---|
| Default runner | `unittest` | `node:test` | `testing` |
| Common modern runner | pytest | Vitest/Jest/node:test | `testing` |
| Mocking | `unittest.mock`, pytest monkeypatch | framework mocks, `node:test` mock, DI | small interfaces/fakes |
| Property testing | Hypothesis | fast-check | built-in fuzzing for supported types, third-party PBT |
| Coverage | coverage.py/pytest-cov | c8, V8 coverage, runner tooling | `go test -cover` |
| Async concern | event loop, task cleanup, fixtures | promises, timers, event loop, workers | goroutines, contexts, races |
| Integration style | pytest fixtures + containers | testcontainers/Docker + local servers | real deps, build tags, containers |
| Concurrency tool | explicit sync, pytest plugins | fake timers, AbortController, workers | `go test -race`, channels, contexts |
| Strength | expressive tests, rich plugins | broad ecosystem, strong UI tooling | simple standard tooling, fast tests |
| Common trap | mock-heavy tests and hidden fixtures | unawaited async and global state | ignored errors and shared parallel state |

### The Final Rule

Every test should earn its place.

A test earns its place when it:

- protects behavior that matters,
- fails for a reason the team cares about,
- runs at the right time,
- can be diagnosed quickly,
- is owned,
- is maintained with the same seriousness as production code.

That is the real definition of comprehensive testing: not the biggest suite, but the most trustworthy feedback system.
