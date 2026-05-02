# Deepening

How to deepen a cluster of shallow modules safely given its dependencies. Uses vocabulary in [LANGUAGE.md](LANGUAGE.md): **module**, **interface**, **seam**, **adapter**.

## Dependency categories

When assessing a deepening candidate, classify dependencies. Category determines how to test the deepened module across its seam.

### 1. In-process

Pure computation or in-memory state; no I/O. Always deepenable: merge modules and test directly through the new interface. No adapter needed.

### 2. Local-substitutable

Dependencies with local test stand-ins (PGLite for Postgres, in-memory filesystem). Deepenable if a stand-in exists. Test the deepened module with the stand-in running in the suite. The seam is internal; no port at the module's external interface.

### 3. Remote but owned (Ports & Adapters)

Your own services across a network (microservices, internal APIs). Define a **port** (interface) at the seam. The deep module owns the logic; inject transport as an **adapter**. Tests use an in-memory adapter; production uses an HTTP/gRPC/queue adapter.

Recommendation shape: *"Define a port at the seam, implement an HTTP adapter for production and an in-memory adapter for testing, so the logic sits in one deep module even though it's deployed across a network."*

### 4. True external (Mock)

Third-party services you don't control (Stripe, Twilio, etc.). The deepened module takes the external dependency as an injected port; tests provide a mock adapter.

## Seam discipline

- **One adapter means a hypothetical seam. Two adapters means a real one.** Don't introduce a port unless at least two adapters are justified (typically production + test). A single-adapter seam is just indirection.
- **Internal seams vs external seams.** A deep module can have internal seams (private to its implementation, used by its own tests) and the external seam at its interface. Don't expose internal seams through the interface just because tests use them.

## Testing strategy: replace, don't layer

- Old unit tests on shallow modules become waste once tests exist at the deepened module's interface; delete them.
- Write new tests at the deepened module's interface. The **interface is the test surface**.
- Assert observable outcomes through the interface, not internal state.
- Tests should survive internal refactors: they describe behaviour, not implementation. If a test must change when implementation changes, it tests past the interface.
