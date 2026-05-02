# Language

Shared vocabulary for all skill suggestions. Use these terms exactly; never substitute "component," "service," "API," or "boundary." Consistency is the point.

## Terms

**Module**
Anything with an interface and implementation. Scale-agnostic: function, class, package, or tier-spanning slice.
_Avoid_: unit, component, service.

**Interface**
Everything a caller must know to use the module correctly: type signature, invariants, ordering constraints,
error modes, required configuration, performance characteristics.
_Avoid_: API, signature (too narrow; only type-level surface).

**Implementation**
Inside a module: its code body. Distinct from **Adapter**: a small adapter can have a large implementation
(Postgres repo), or a large adapter can have a small implementation (in-memory fake). Use "adapter" when the
seam is the topic; "implementation" otherwise.

**Depth**
Leverage at the interface: behaviour a caller/test can exercise per unit of interface they must learn. A
module is **deep** when much behaviour sits behind a small interface; **shallow** when its interface is nearly
as complex as its implementation.

**Seam** _(from Michael Feathers)_
Where you can alter behaviour without editing there: the *location* of a module's interface. Seam placement is
a design decision distinct from what goes behind it.
_Avoid_: boundary (overloaded with DDD's bounded context).

**Adapter**
Concrete thing satisfying an interface at a seam. Describes *role* (slot filled), not substance (what's inside).

**Leverage**
What callers get from depth: more capability per unit of interface they must learn. One implementation pays back across N call sites and M tests.

**Locality**
What maintainers get from depth: change, bugs, knowledge, and verification concentrated in one place, not spread across callers. Fix once, fixed everywhere.

## Principles

- **Depth is a property of the interface, not the implementation.** A deep module can internally compose
  small, mockable, swappable parts; they aren't part of the interface. A module can have **internal seams**
  (private to its implementation, used by its own tests) and the **external seam** at its interface.

- **The deletion test.** Imagine deleting the module. If complexity vanishes, the module hid nothing
  (pass-through). If complexity reappears across N callers, the module earned its keep.

- **The interface is the test surface.** Callers and tests cross the same seam. If you want to test *past* the
  interface, the module probably has the wrong shape.

- **One adapter means a hypothetical seam. Two adapters means a real one.** Introduce a seam only when something actually varies across it.

## Relationships

- A **Module** has exactly one **Interface**: its surface for callers and tests.

- **Depth** is a **Module** property measured against its **Interface**.

- A **Seam** is where a **Module**'s **Interface** lives.

- An **Adapter** sits at a **Seam** and satisfies the **Interface**.

- **Depth** produces **Leverage** for callers and **Locality** for maintainers.

## Rejected framings

- **Depth as ratio of implementation-lines to interface-lines** (Ousterhout): rewards padding the implementation. Use depth-as-leverage instead.

- **"Interface" as the TypeScript `interface` keyword or a class's public methods**: too narrow; interface here includes every fact a caller must know.

- **"Boundary"**: overloaded with DDD's bounded context. Say **seam** or **interface**.
