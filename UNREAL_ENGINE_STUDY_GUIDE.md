# Unreal Engine — A Depth-First Guide for Engineers

A practical, depth-first guide to Unreal Engine 5 for developers who want to understand *how the engine actually works*, not just which buttons to click. It assumes you can program (the C++ chapters assume C++ familiarity, but the rest does not) and that you have basic 3D intuition — what a mesh, material, and camera are. If you need the 3D foundation first, read the [Blender conceptual guide](BLENDER_STUDY_GUIDE.md) for content creation or the [WebGL/OpenGL guide](WEBGL_OPENGL_STUDY_GUIDE.md) for the rendering pipeline underneath. This guide covers the engine's architecture, the Actor/Component model, Blueprints *and* C++ (and the gameplay framework that unifies them), the UE5 rendering stack (Nanite, Lumen, Virtual Shadow Maps), animation, physics, audio, UI, networking/replication, and the performance discipline that separates a prototype from a shipped game.

Primary references: [Unreal Engine Documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine), [Unreal Engine C++ API](https://dev.epicgames.com/documentation/en-us/unreal-engine/API), [Epic Developer Community](https://dev.epicgames.com/community/), [Unreal Source on GitHub](https://github.com/EpicGames/UnrealEngine) (requires linking your Epic account).

---

## Table of Contents

1. [The Mental Model](#1-the-mental-model)
2. [Project Setup & The Editor](#2-project-setup--the-editor)
3. [The Object Model — UObject, Actor, Component](#3-the-object-model--uobject-actor-component)
4. [The Gameplay Framework](#4-the-gameplay-framework)
5. [Blueprints](#5-blueprints)
6. [C++ in Unreal](#6-c-in-unreal)
7. [Blueprint ↔ C++ Interop](#7-blueprint--c-interop)
8. [The Reflection System & Memory](#8-the-reflection-system--memory)
9. [Rendering — Nanite, Lumen, and the Frame](#9-rendering--nanite-lumen-and-the-frame)
10. [Materials](#10-materials)
11. [Animation](#11-animation)
12. [Physics & Collision](#12-physics--collision)
13. [Input](#13-input)
14. [UI — UMG & Slate](#14-ui--umg--slate)
15. [Audio](#15-audio)
16. [Networking & Replication](#16-networking--replication)
17. [Assets, Cooking & Packaging](#17-assets-cooking--packaging)
18. [Performance & Profiling](#18-performance--profiling)
19. [Patterns & Recipes](#19-patterns--recipes)
20. [Mastery Checklist](#20-mastery-checklist)
21. [Additional Resources](#21-additional-resources)

---

## 1. The Mental Model

### What Unreal Engine Is

Unreal Engine is a **C++ game engine with an editor and two scripting surfaces**. The C++ core provides the runtime: an object system, a renderer, a physics engine, an audio engine, a networking layer, and a gameplay framework that ties them together. On top of that sits **Blueprint**, a visual scripting language that compiles to bytecode run by a virtual machine. Both Blueprint and C++ manipulate the same objects through the same reflection system. There is no "Blueprint world" and "C++ world" — there is one object graph, exposed two ways.

The single most important fact about Unreal: **it is not a library you call, it is a framework that calls you.** You do not write a `main()` and pump a loop. You subclass engine classes — `AActor`, `APawn`, `UActorComponent` — and override virtual functions (`BeginPlay`, `Tick`, `EndPlay`) that the engine invokes at the right time. Your code lives inside the engine's lifecycle, not around it.

### The Four Layers

```
┌─────────────────────────────────────────────────────────┐
│  Your game: Blueprints + C++ gameplay classes            │  ← you write this
├─────────────────────────────────────────────────────────┤
│  Gameplay Framework: GameMode, PlayerController,         │  ← you subclass this
│  Pawn, Character, GameState, PlayerState, HUD            │
├─────────────────────────────────────────────────────────┤
│  Engine subsystems: Renderer, Physics (Chaos), Audio,    │  ← you configure this
│  Animation, Networking, AI, Input                        │
├─────────────────────────────────────────────────────────┤
│  Core: UObject system, reflection, GC, serialization,    │  ← you rely on this
│  reflection (UCLASS/UPROPERTY/UFUNCTION), modules        │
└─────────────────────────────────────────────────────────┘
```

Almost everything distinctive about Unreal — garbage collection, Blueprint exposure, network replication, the editor's property panels, save/load — is built on the **reflection system** at the bottom. When you write `UPROPERTY()` above a member variable, you are not adding metadata for documentation; you are registering that field with the engine so the GC can see it, the editor can display it, the serializer can save it, and the network can replicate it. Chapter 8 is the one that makes the rest click.

### Blueprint vs C++ — The Real Tradeoff

This is the question every newcomer asks, and the honest answer is **both, by design**:

| Concern | Blueprint | C++ |
|---|---|---|
| Iteration speed | Instant (hot-reload in editor) | Slower (compile + reload) |
| Performance | VM bytecode, ~10× slower per node | Native, compiled |
| Designer accessibility | High — visual, no toolchain | Low — needs IDE + build |
| Complex logic / data structures | Painful past a point | Natural |
| Merge/diff in version control | Binary, hard to merge | Text, normal diffs |
| Frame-by-frame `Tick` work | Avoid | Fine |

The shipping pattern Epic itself uses: **systems and performance-critical logic in C++, composition and tuning in Blueprint.** A weapon's firing math, hit registration, and replication live in a C++ base class; the specific rifle's fire rate, muzzle effect, and sound are set on a Blueprint subclass a designer can edit without touching code. This "C++ base, Blueprint derived" split appears throughout the guide.

### Why It Feels Different From Other Engines

If you're coming from Unity, the closest analogies: `GameObject` ≈ `Actor`, `MonoBehaviour` ≈ `UActorComponent`, prefab ≈ Blueprint class, `Instantiate` ≈ `SpawnActor`. The deepest difference is that Unity's `GameObject` is a thin container and behavior lives in components, whereas Unreal's `Actor` is itself a substantial class with its own lifecycle, and the engine's gameplay framework (`GameMode`, `Controller`, `Pawn`) imposes far more structure out of the box. Unreal is more opinionated; you get more for free and fight the framework more when you go against its grain.

---

## 2. Project Setup & The Editor

### Installing

Unreal Engine is distributed through the **Epic Games Launcher** (Windows/macOS) or built from source on GitHub. For C++ work you also need a compiler toolchain:

- **Windows:** Visual Studio 2022 with the "Game development with C++" workload, plus the "Unreal Engine installer" component.
- **macOS:** Xcode (latest).
- **Linux:** Clang via the cross-compile toolchain or a source build.

Source builds (from `github.com/EpicGames/UnrealEngine`, after linking your GitHub account to Epic) matter when you need engine modifications, want to step into engine code in the debugger, or are shipping on a console. Most teams start with the launcher binary and move to source if needed.

### Creating a Project

The New Project dialog asks two questions that matter:

1. **Blueprint or C++?** This only sets up the initial files. A Blueprint project can add C++ later (right-click in Content Browser → New C++ Class), and a C++ project always supports Blueprints. The C++ template generates a `Source/` folder, a `.uproject`, and module files.
2. **Template.** Templates (Third Person, First Person, Top Down, Blank) pre-wire the gameplay framework so you start with a controllable character. The Third Person template is the best teaching tool — it contains a `Character`, an `Enhanced Input` setup, an animation Blueprint, and a `GameMode`, all of which this guide explains.

### Anatomy of a Project on Disk

```
MyProject/
├── MyProject.uproject        # JSON manifest: engine version, modules, plugins
├── Config/                   # .ini files — the engine's settings layers
│   ├── DefaultEngine.ini
│   ├── DefaultGame.ini
│   └── DefaultInput.ini
├── Content/                  # ALL assets (.uasset, .umap) — binary, opaque
├── Source/                   # C++ (only in C++ projects)
│   └── MyProject/
│       ├── MyProject.Build.cs        # module build rules (C#!)
│       ├── MyProject.cpp / .h
│       └── ... your classes
├── Plugins/                  # project-local plugins
├── Binaries/                 # compiled output (git-ignore)
├── Intermediate/             # generated code, build temp (git-ignore)
├── DerivedDataCache/         # cooked/compiled asset cache (git-ignore)
└── Saved/                    # logs, autosaves, config overrides (git-ignore)
```

Two non-obvious points. First, **build configuration is C#, not a Makefile.** `MyProject.Build.cs` declares module dependencies (`PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", ... })`) and is executed by **UnrealBuildTool (UBT)**, Epic's build orchestrator. Second, **`Content/` is binary and unmergeable.** A `.uasset` is a serialized `UObject` graph. This is why teams use locking version control (Perforce) or are disciplined about who edits which assets in Git — you cannot merge two people's changes to the same Blueprint.

### The .gitignore That Matters

Only `Config/`, `Content/`, `Source/`, `Plugins/`, and the `.uproject` are source-of-truth. Everything else is generated:

```gitignore
Binaries/
DerivedDataCache/
Intermediate/
Saved/
*.sln
*.VC.db
```

For binary assets, [Git LFS](https://git-lfs.com/) is standard. Large teams use Perforce because of file locking on unmergeable assets.

### The Editor — The Panels You Live In

- **Viewport** — the 3D scene. Learn the navigation: right-mouse + WASD to fly, F to focus selection, Alt+drag to orbit. The `~` key opens the console (`stat fps`, `stat unit`, and dozens of debug commands).
- **Outliner** — the tree of every Actor in the level.
- **Details panel** — every `UPROPERTY` of the selected object, generated from reflection. This *is* the reflection system made visible.
- **Content Browser** — your asset database. Right-click is the gateway to creating everything.
- **Place Actors** — drag lights, meshes, volumes into the world.

### Play-In-Editor (PIE) and the Game Instance Lifecycle

Pressing **Play** runs the game inside the editor process (PIE). This is fast but lies in two ways you must internalize:

1. **PIE shares the editor's memory and some global state.** Static variables persist between PIE sessions; a real standalone build resets them. Bugs that only appear in packaged builds often trace to this.
2. **PIE can simulate multiplayer** by spawning multiple windows/clients in one process (Net Mode dropdown). This is invaluable for testing replication (Chapter 16) without deploying.

"Standalone Game" launches a separate process — closer to shipping behavior. Always test in Standalone and in a packaged build before trusting that something works.

---

## 3. The Object Model — UObject, Actor, Component

### The Class Hierarchy

Everything that participates in the engine's managed systems descends from **`UObject`**. It is the root that provides reflection, garbage collection, serialization, and Blueprint/network exposure. The key subtree:

```
UObject                         # GC, reflection, serialization — the base of everything
├── AActor                      # something that can be placed in a level (the 'A' prefix)
│   ├── APawn                   # an Actor that can be "possessed" and controlled
│   │   └── ACharacter          # a Pawn with a capsule, movement component, and skeletal mesh
│   ├── AController             # the "brain" that possesses a Pawn
│   │   ├── APlayerController    # a human's brain
│   │   └── AAIController        # an AI's brain
│   ├── AGameModeBase           # rules of the game (server-only)
│   ├── APlayerState / AGameStateBase
│   └── AHUD, AInfo, ...
├── UActorComponent             # behavior/data attached to an Actor (no transform)
│   └── USceneComponent         # a component WITH a transform (position/rotation/scale)
│       ├── UPrimitiveComponent  # something renderable/collidable
│       │   ├── UStaticMeshComponent
│       │   ├── USkeletalMeshComponent
│       │   └── UShapeComponent (box, sphere, capsule)
│       └── UCameraComponent, ULightComponent, ...
└── UActorComponent, UDataAsset, UUserWidget, ... (non-Actor UObjects)
```

**The naming prefixes are mandatory and meaningful:** `U` for `UObject` subclasses, `A` for `AActor` subclasses, `F` for plain structs/non-UObject types (`FVector`, `FString`), `I` for interfaces, `E` for enums, `T` for templates (`TArray`, `TSubclassOf`). The code generator (UHT) relies on these prefixes; getting them wrong breaks compilation.

### Actor vs Component — The Composition Model

An **Actor** is a thing that exists in a level. A **Component** is a reusable piece of behavior or data that lives inside an Actor. This is composition over inheritance, the same instinct as Unity's components, but with a twist:

- **`UActorComponent`** — pure behavior/data, *no position in the world*. Example: a `UHealthComponent` that tracks HP. It doesn't have a location because "health" isn't somewhere in space.
- **`USceneComponent`** — has a **transform** (location, rotation, scale) and can be attached to other scene components, forming a hierarchy. A car Actor has a root scene component, with a mesh, four wheel meshes, a camera, and an audio component attached at offsets.
- **`UPrimitiveComponent`** — a scene component that can be rendered and/or collide. Static meshes, skeletal meshes, and collision shapes.

Every Actor has exactly one **root component**. The root's transform *is* the Actor's transform; everything else attaches beneath it and inherits its movement. Move the root, everything follows.

```cpp
// A typical Actor composed of components (C++ constructor)
ADrone::ADrone()
{
    // RootComponent is the anchor; all else attaches under it.
    RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));

    Body = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
    Body->SetupAttachment(RootComponent);

    SpringArm = CreateDefaultSubobject<USpringArmComponent>(TEXT("SpringArm"));
    SpringArm->SetupAttachment(RootComponent);
    SpringArm->TargetArmLength = 300.f;

    Camera = CreateDefaultSubobject<UCameraComponent>(TEXT("Camera"));
    Camera->SetupAttachment(SpringArm);  // camera rides the spring arm

    Health = CreateDefaultSubobject<UHealthComponent>(TEXT("Health")); // no transform
}
```

### The Actor Lifecycle

This is the set of virtual functions the engine calls on your Actor, in order. Knowing *when* each fires prevents an entire category of bugs (accessing things before they exist):

```
Spawn / Level Load
   │
   ▼
PostInitializeComponents()   # components exist and are registered
   │
   ▼
BeginPlay()                  # gameplay has started; safe to reference other Actors,
   │                         #   bind events, start timers. THE main entry point.
   ▼
Tick(DeltaSeconds)           # called every frame (if ticking enabled)
   │  ...repeats...
   ▼
EndPlay(Reason)              # leaving play: destroyed, level change, PIE stop
   │
   ▼
BeginDestroy() → garbage collected
```

The rookie mistake is putting initialization in the **constructor** that depends on other Actors or the world. The constructor runs when the object is created — possibly during editor load, possibly before the world is fully set up. **`BeginPlay` is where gameplay initialization belongs.** Constructors should only set defaults and create components.

### Tick — and Why You Should Avoid It

`Tick` runs every frame. It's the obvious place to put per-frame logic, and it's also the most abused feature in the engine. A thousand Actors each doing trivial work in `Tick` is a thousand virtual function calls and a measurable cost. The discipline:

- **Disable ticking** when you don't need it: `PrimaryActorTick.bCanEverTick = false;` (the default for many component types).
- **Prefer events and timers** over polling in `Tick`. Instead of checking `if (Health <= 0)` every frame, fire a delegate when damage is applied.
- **Use timers** (`GetWorldTimerManager().SetTimer(...)`) for periodic work that doesn't need frame granularity — a status effect that pulses every 0.5s doesn't need 60 checks per second.
- If you must tick, **tick less often** with `PrimaryActorTick.TickInterval`.

This connects directly to performance (Chapter 18): Tick cost is one of the first things a profiler reveals.

### Spawning and Destroying Actors

You don't `new` an Actor — the world owns them and the GC tracks them. You ask the world to spawn:

```cpp
FActorSpawnParameters Params;
Params.Owner = this;
AProjectile* Shot = GetWorld()->SpawnActor<AProjectile>(
    ProjectileClass,            // a UClass* / TSubclassOf<AProjectile>
    MuzzleLocation,
    MuzzleRotation,
    Params);

// Later:
Shot->Destroy();   // marks for destruction; GC reclaims memory
```

`TSubclassOf<AProjectile>` is a type-safe class reference — it guarantees the assigned class is a `AProjectile` or subclass, and it's how you let a designer pick *which* projectile Blueprint to spawn from a dropdown in the editor.

---

## 4. The Gameplay Framework

The gameplay framework is Unreal's biggest opinion: a set of cooperating classes that answer "who controls what, who decides the rules, and where does state live." Fighting it is the cause of most architectural pain. Learning it is the highest-leverage thing in this guide.

### The Cast of Classes

```
            GameMode (server only) ── owns the rules, spawns players, sets win/lose
                  │
   spawns &       │
   assigns        ▼
            PlayerController ◄──── the player's "brain": input, camera, UI ownership
                  │  possesses
                  ▼
                Pawn / Character ◄── the physical body in the world (visual + movement)
                  │
                  ├── PlayerState  ── per-player data that must survive respawn (score, name)
                  │
            GameState ──────────── per-match data every client needs (scores, match phase)
```

The mental model: **a Controller possesses a Pawn.** The Pawn is the body; the Controller is the will. This separation is powerful — when a player dies, the Pawn is destroyed but the PlayerController persists, then possesses a freshly spawned Pawn. An AI uses the *same* Pawn class; only the controlling class differs (`AAIController` instead of `APlayerController`). Swap the controller and a player-driven character becomes AI-driven with zero changes to the Pawn.

### Each Class, Concretely

- **`Pawn`** — anything controllable. A character, a vehicle, a turret, a flying drone. The minimal Pawn has a collision component, a visual, and accepts input. **`Character`** is a specialized Pawn for bipedal humanoids: it bundles a capsule collider, a `UCharacterMovementComponent` (walking, jumping, swimming, network-smoothed), and a skeletal mesh. Use `Character` for anything that walks; subclass `Pawn` directly for vehicles and oddities.

- **`Controller`** — the brain, with **no physical presence**. `APlayerController` handles a human: it owns the camera management, processes input, and is the gateway to the player's UI and the network connection. `AAIController` runs behavior trees and navigation. A controller can possess and unpossess pawns at runtime.

- **`GameMode`** (`AGameModeBase`) — the **server-authoritative rulebook**. It exists *only on the server* (and in single-player). It decides which Pawn class to spawn, where players start, what the win condition is, what happens on death. Clients never see the GameMode — asking for it on a client returns null. This is a deliberate security boundary: rules live where they can't be tampered with.

- **`GameState`** (`AGameStateBase`) — match-wide state that **every client needs to know**: the current score, the match phase (warmup/active/ended), the list of connected players. It's replicated to all clients. Where GameMode is the server's private rulebook, GameState is the public scoreboard.

- **`PlayerState`** — per-player state that must **survive the player's Pawn being destroyed**: name, score, team, ping. When you respawn, your Pawn is new but your PlayerState (and your score) persists. Replicated to all clients so everyone can see everyone's score.

- **`HUD` / UMG** — the on-screen UI. Modern projects use UMG widgets (Chapter 14) owned by the PlayerController rather than the legacy `AHUD` canvas drawing.

### Why This Split Exists — A Worked Example

Consider a respawn in a shooter. Walk the classes:

1. Player's `Character` takes lethal damage. The `Character` (Pawn) is destroyed.
2. The `PlayerController` survives — it's the persistent connection to the human. So does the `PlayerState` (the score stays).
3. The `PlayerController` notifies the `GameMode` (server-only logic): "my pawn died."
4. The `GameMode` decides the respawn rules — delay, location (`PlayerStart` actors), which Pawn class.
5. After the delay, the `GameMode` spawns a fresh `Character` and tells the `PlayerController` to **possess** it.
6. `GameState` already reflected the death in the match score; every client saw it via replication.

No single class does everything. Each owns one concern. This is why the framework feels heavyweight at first and indispensable once you've built something real with networking.

### A Minimal GameMode in C++

```cpp
// The rulebook: which classes to use for this match.
AArenaGameMode::AArenaGameMode()
{
    DefaultPawnClass    = AArenaCharacter::StaticClass();
    PlayerControllerClass = AArenaPlayerController::StaticClass();
    PlayerStateClass    = AArenaPlayerState::StaticClass();
    GameStateClass      = AArenaGameState::StaticClass();
}

void AArenaGameMode::OnPlayerDied(AController* DeadController)
{
    // Server-authoritative respawn after a delay.
    FTimerHandle Handle;
    FTimerDelegate Del;
    Del.BindUObject(this, &AArenaGameMode::RespawnPlayer, DeadController);
    GetWorldTimerManager().SetTimer(Handle, Del, RespawnDelay, false);
}
```

You almost always set these classes on a **Blueprint subclass of your GameMode** so designers can swap them, then assign that Blueprint in Project Settings → Maps & Modes (or per-level via a World Settings override).

---

## 5. Blueprints

Blueprint is Unreal's visual scripting system. Despite the "no-code" framing, it is a real programming language — it has variables, functions, types, control flow, and an object model. It compiles to bytecode executed by the **Blueprint VM**. Understanding it as "a language with a graph syntax" rather than "drag-and-drop magic" is the right frame.

### What a Blueprint Class Is

A Blueprint asset is most often a **subclass of a C++ (or another Blueprint) class**, with overridden behavior and configured properties. `BP_Rifle` might subclass `AWeapon` (C++), set its mesh and fire rate, and override the `Fire` event with a node graph. It's the exact analog of writing a subclass in code — Epic's editor just gives designers a way to do it without a compiler.

### The Anatomy of the Graph

- **Execution pins (white, ►)** — the control flow. The white line threading through nodes is "what runs next." This is the program counter made visible.
- **Data pins (colored)** — typed values. Blue = object reference, red = boolean, green = float, etc. You drag from an output data pin to an input to wire values.
- **Event nodes** — entry points: `Event BeginPlay`, `Event Tick`, `Event ActorBeginOverlap`, custom events, input events. Execution starts here.
- **Functions vs Events** — functions can return values and run synchronously; events cannot return values but can be called over the network and can contain latent (async) nodes.
- **Variables** — typed, with the same `UPROPERTY` flags as C++ (editable, replicated, private). The "eye" icon exposes a variable to the editor's Details panel.

### Key Node Categories

- **Flow control:** `Branch` (if), `Sequence` (do A then B then C), `ForLoop`, `ForEachLoop`, `Gate`, `DoOnce`, `FlipFlop`, `Switch`.
- **Latent / async nodes** — nodes with a clock icon that span multiple frames: `Delay`, `Timeline`, `Move Component To`, async asset loads. These can only live in Events, not functions, because functions must complete in one call.
- **Timelines** — a Blueprint-only construct: a built-in keyframe track that drives a value over time (a curve), perfect for door-opening, fades, and lerps without writing tick math.
- **Cast nodes** — `Cast To BP_Door`: a runtime type check that, if successful, gives you the typed reference. Overusing casts creates hard references that bloat memory (the cast forces the target class to load); prefer interfaces (below).

### Communication Between Blueprints

Three patterns, in increasing decoupling:

1. **Direct reference + cast** — you have a reference to the other object and cast to its type to call its functions. Simple, but creates a hard dependency.
2. **Blueprint Interfaces** — declare a set of functions (an interface), implement it on multiple unrelated classes, and call through the interface without knowing the concrete type. The decoupled choice: a `BP_Switch` calls `Interact()` on whatever it hit, be it a door, a chest, or an NPC, none of which it references directly.
3. **Event Dispatchers (delegates)** — the observer pattern. An object broadcasts an event ("I died", "health changed") and any number of listeners subscribe. The publisher knows nothing about subscribers. This is how a health bar widget updates when a character takes damage without the character ever referencing the UI.

### Blueprint Performance Reality

The VM adds overhead per node — roughly an order of magnitude slower than equivalent C++ per operation. This is irrelevant for event-driven logic that fires occasionally (opening a door) and very relevant for per-frame math over many objects (a `Tick` graph doing vector math on 500 actors). The rule: **Blueprint for orchestration and configuration, C++ for hot loops and heavy math.** "Nativization" (compiling Blueprints to C++) existed in UE4 but was removed in UE5; the answer now is to move hot logic to C++ directly.

A subtle cost: **hard references.** A Blueprint that references another asset (a mesh, a sound, another Blueprint) forces that asset to load into memory whenever the referencing Blueprint loads. A web of casts and direct references can pull half your content into memory at once. Use **soft references** (`TSoftObjectPtr`, soft class pointers) and async loading for things you don't always need.

---

## 6. C++ in Unreal

Unreal C++ is C++ with a heavy macro and code-generation layer. You will recognize the language but not the idioms — Epic has its own containers, string types, smart pointers, and a reflection preprocessor. Writing it like standard C++ fights the engine.

### The Macros That Aren't Optional

```cpp
// MyActor.h
#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MyActor.generated.h"   // ALWAYS last include; UHT generates this

UCLASS(Blueprintable)            // register this class with the reflection system
class MYGAME_API AMyActor : public AActor
{
    GENERATED_BODY()             // injects generated boilerplate; mandatory

public:
    AMyActor();

    // Exposed to the editor's Details panel and to Blueprint.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat")
    float MaxHealth = 100.f;

    // A UObject pointer the GC must track — UPROPERTY makes it visible to GC.
    UPROPERTY(VisibleAnywhere)
    UStaticMeshComponent* Mesh;

    // Callable from Blueprint graphs.
    UFUNCTION(BlueprintCallable, Category="Combat")
    void ApplyDamage(float Amount);

protected:
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
};
```

What each macro does:

- **`UCLASS()`** — registers the class with the reflection system so it can be spawned by name, exposed to Blueprint, serialized, and GC-tracked. Specifiers like `Blueprintable` (can be subclassed in BP) and `Abstract` tune behavior.
- **`GENERATED_BODY()`** — expands (via the generated `.generated.h`) into constructors, reflection registration, and the glue the engine needs. Without it, the class won't link.
- **`UPROPERTY()`** — the workhorse. Registers a member with reflection. The specifiers control four independent systems: editor visibility (`EditAnywhere`/`VisibleAnywhere`), Blueprint access (`BlueprintReadWrite`/`BlueprintReadOnly`), serialization, and GC tracking. **A `UObject*` pointer without `UPROPERTY()` is invisible to the GC and will be collected out from under you — a use-after-free.** This is the single most important rule in Unreal C++.
- **`UFUNCTION()`** — exposes a function to Blueprint, networking (`Server`/`Client`/`NetMulticast`), or as an event (`BlueprintImplementableEvent`).

`MYGAME_API` is the module's export macro (DLL boundary); it must prefix classes other modules use.

### Unreal's Standard Library — Use It, Not std::

Unreal predates and replaces much of the STL for engine reasons (memory control, serialization, platform portability):

| Standard C++ | Unreal | Notes |
|---|---|---|
| `std::vector` | `TArray<T>` | The default container. Contiguous, fast. |
| `std::map` | `TMap<K,V>` | Hashed map. `TSortedMap` for ordered. |
| `std::set` | `TSet<T>` | Hashed set. |
| `std::string` | `FString` | Mutable, owns memory. For manipulation. |
| string literal/key | `FName` | Interned, immutable, fast compare. For asset/bone names. |
| display text | `FText` | Localized, for anything a user reads. |
| `std::shared_ptr` | `TSharedPtr<T>` | For non-UObject types only. |
| `std::unique_ptr` | `TUniquePtr<T>` | For non-UObject types only. |
| `std::weak_ptr` | `TWeakPtr<T>` / `TWeakObjectPtr<T>` | The latter for UObjects. |
| raw `new`/`delete` | `NewObject<T>()` / `SpawnActor` | Never `new` a UObject. |

**The string type trilemma trips up everyone.** `FString` is a mutable string you build and slice. `FName` is an interned, case-insensitive, immutable handle — comparisons are integer compares, used for bone names, asset names, tags (cheap to compare millions of times). `FText` is localizable display text — anything the player reads must be `FText` so it can be translated. Using `FString` for UI text or `FName` where you needed manipulation is a common smell.

### Memory: Two Worlds

This is the crux of Unreal C++. There are **two memory regimes** and you must know which one a type lives in:

1. **`UObject` and subclasses (including all Actors and Components)** are **garbage collected**. You never `delete` them. You create them with `NewObject<T>()` or `SpawnActor<T>()`. The GC keeps them alive as long as something reachable holds a `UPROPERTY` reference to them. Drop all `UPROPERTY` references and they're collected. **Do not use `TSharedPtr` on UObjects** — it conflicts with the GC.

2. **Plain C++ types (`F`-structs, your own non-UObject classes)** are *not* GC-managed. Manage them with RAII, `TUniquePtr`/`TSharedPtr`, or stack allocation, like normal C++.

The classic bug: storing a `UObject*` as a raw member without `UPROPERTY()`. The GC can't see the reference, collects the object during the next sweep, and your pointer dangles. The fix is always the same: mark it `UPROPERTY()`. For non-owning references that should *not* keep the object alive, use `TWeakObjectPtr<T>` and check `IsValid()` before dereferencing.

```cpp
UPROPERTY()                              // GC sees this; object stays alive
UStaticMeshComponent* Mesh;

TWeakObjectPtr<AActor> LastAttacker;     // does NOT keep it alive
// ... later
if (LastAttacker.IsValid()) { LastAttacker->TakeDamage(...); }
```

### Logging and Assertions

```cpp
UE_LOG(LogTemp, Warning, TEXT("Health is now %f for %s"), Health, *GetName());
// *GetName() — the leading * converts FString to const TCHAR* for %s

check(Mesh != nullptr);        // hard assert; crashes in all builds if false
ensure(Health >= 0.f);         // soft assert; logs + continues, once per call site
```

Define your own log categories (`DECLARE_LOG_CATEGORY_EXTERN`) instead of spamming `LogTemp`. `check` vs `ensure` matters: `check` halts execution (use for invariants that mean the program is broken), `ensure` reports but continues (use for "shouldn't happen but recoverable").

---

## 7. Blueprint ↔ C++ Interop

The power of Unreal's architecture is the seam between C++ and Blueprint. The standard professional pattern — **C++ base class, Blueprint derived class** — depends entirely on exposing the right things across this seam. Here are the tools.

### Exposing C++ to Blueprint

```cpp
// A value a designer can tune in the Blueprint's Details panel.
UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Weapon")
float FireRate = 0.1f;

// A function a designer can call from a Blueprint graph.
UFUNCTION(BlueprintCallable, Category="Weapon")
void Reload();

// A pure getter (no exec pins, like a const accessor) shown in BP.
UFUNCTION(BlueprintPure, Category="Weapon")
float GetAmmoFraction() const;
```

### Calling Blueprint from C++ — Two Directions

```cpp
// 1. BlueprintImplementableEvent: declared in C++, IMPLEMENTED in Blueprint.
//    C++ calls it; the body is a BP graph. No C++ body exists.
UFUNCTION(BlueprintImplementableEvent, Category="FX")
void OnFired();   // designer wires muzzle flash + sound in the BP

// 2. BlueprintNativeEvent: a C++ default that Blueprint CAN override.
UFUNCTION(BlueprintNativeEvent, Category="Combat")
void OnDamaged(float Amount);
void OnDamaged_Implementation(float Amount);  // the C++ default; note the suffix
```

`BlueprintImplementableEvent` is "C++ defines the hook, designer fills it in" — perfect for visual/audio polish that has no sensible C++ default. `BlueprintNativeEvent` is "C++ has a default behavior, designer may override it" — note the mandatory `_Implementation` suffix on the C++ body.

### The Professional Split, Concretely

```
AWeapon  (C++)                     BP_PlasmaRifle  (Blueprint, subclass of AWeapon)
├── FireRate, Damage, Ammo         ├── FireRate = 0.05  (set in Details)
│     (UPROPERTY EditAnywhere)     ├── Mesh = SK_PlasmaRifle  (assigned asset)
├── Fire()  — hit math, recoil,    ├── OnFired event → spawn Niagara muzzle FX,
│     replication (BlueprintCallable)│     play sound, camera shake
└── OnFired()  — BlueprintImplementableEvent (empty in C++)
```

The C++ class owns *correctness and performance* (hit registration, damage, network replication). The Blueprint subclass owns *content and feel* (which mesh, which sound, how the muzzle flash looks, the exact fire rate). A designer iterates on the Blueprint all day without ever recompiling C++, and the C++ programmer changes hit math without touching art. This division of labor is the entire point of Unreal's two-language design.

### `TSubclassOf` — Letting Designers Pick Classes

```cpp
// Designer picks WHICH projectile Blueprint to spawn, from a dropdown
// filtered to AProjectile subclasses.
UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Weapon")
TSubclassOf<AProjectile> ProjectileClass;
```

This is how data-driven design works in Unreal: C++ says "I will spawn *a* projectile," and the Blueprint says *which* projectile, chosen from a type-safe dropdown.

---

## 8. The Reflection System & Memory

Everything distinctive about Unreal flows from one system: **reflection**, the engine's ability to know the structure of your types at runtime. This chapter is the keystone — once you see how reflection underlies GC, serialization, the editor, networking, and Blueprint, the rest of the engine stops feeling like magic.

### What Reflection Is and How It's Built

Reflection is runtime metadata: a description of every `UCLASS`, its `UPROPERTY` fields (names, types, flags), and its `UFUNCTION`s. C++ has no native reflection, so Unreal generates it with a build step.

```
Your .h files with UCLASS/UPROPERTY/UFUNCTION macros
        │
        ▼
UnrealHeaderTool (UHT)  ── parses your headers BEFORE the C++ compiler runs
        │
        ▼
Generated .gen.cpp / .generated.h  ── tables describing your types
        │
        ▼
C++ compiler + linker  ── compiles your code AND the generated reflection tables
        │
        ▼
At runtime: UClass objects describe every type; the engine queries them
```

The macros (`UCLASS`, etc.) are *markers* UHT scans for. They expand to nearly nothing for the compiler; their real job is to tell UHT "generate reflection data for this." This is why the `#include "MyClass.generated.h"` must be last and why forgetting `GENERATED_BODY()` breaks the build — they're hooks into generated code.

### The Five Systems Reflection Powers

1. **Garbage collection.** The GC walks `UPROPERTY` references to determine reachability. It can only see object pointers you've marked. (Hence the cardinal rule from Chapter 6.)
2. **Serialization.** Saving a level, a save game, or a `.uasset` means walking reflected properties and writing them out. `UPROPERTY` fields persist; un-reflected fields don't.
3. **The editor.** The Details panel is generated entirely from reflection — every row is a `UPROPERTY`, with the widget chosen by its type and the editability set by its specifiers.
4. **Blueprint.** Blueprint can only see and call what reflection exposes (`BlueprintReadWrite`, `BlueprintCallable`). The Blueprint VM dispatches through reflection tables.
5. **Networking.** Replication (Chapter 16) walks reflected properties marked `Replicated` and sends the changed ones. RPCs are reflected `UFUNCTION`s.

One mechanism, five payoffs. This is why the macros are non-negotiable: opting out of reflection opts out of being a first-class engine citizen.

### Garbage Collection in Depth

Unreal's GC is a **mark-and-sweep** collector that runs periodically (default ~every 60s, plus on demand under memory pressure). It works in two phases:

1. **Mark:** starting from a set of roots (objects added to the "root set," plus the reachability graph from them), it walks all `UPROPERTY` object references and marks everything reachable.
2. **Sweep:** anything unmarked is unreachable — it gets destroyed (`BeginDestroy`) and its memory reclaimed.

Implications:

- **`Destroy()` is not immediate free.** `Actor->Destroy()` removes it from the world and unhooks it, but the memory is reclaimed at the next GC pass. Don't assume the destructor ran synchronously.
- **To keep a UObject alive that nothing else references**, add it to the root set (`AddToRoot()`) or hold a `UPROPERTY` reference. Forget, and it vanishes at the next sweep.
- **To reference without keeping alive**, use `TWeakObjectPtr` and check `IsValid()`. This is the right tool for "the last actor that hit me" — you don't want to keep a corpse in memory just because something pointed at it.

```cpp
UPROPERTY()
TArray<AEnemy*> ActiveEnemies;   // GC sees every element; all stay alive

TWeakObjectPtr<APawn> Target;    // tracked but not kept alive
if (APawn* T = Target.Get())     // safe deref pattern
{
    T->Jump();
}
```

`TObjectPtr<T>` is the modern (UE5) replacement for raw `UPROPERTY` pointers — it behaves like a raw pointer at runtime but enables access tracking and lazy loading in the editor. New code should prefer `TObjectPtr<UStaticMeshComponent>` over `UStaticMeshComponent*` for `UPROPERTY` members.

### Soft vs Hard References — The Memory Budget Lever

- **Hard reference** (`TObjectPtr<T>`, direct BP reference): loading the owner loads the target. Eager.
- **Soft reference** (`TSoftObjectPtr<T>`, `TSoftClassPtr<T>`): stores a *path*, not a loaded object. The target loads only when you explicitly request it. Lazy.

For a boss that appears once, a hard reference from your level Blueprint keeps the boss's mesh, textures, and sounds in memory the entire game. A soft reference loads them only when you spawn the boss. On memory-constrained platforms, soft references and async loading are the difference between fitting in budget and crashing.

---

## 9. Rendering — Nanite, Lumen, and the Frame

UE5's rendering is the engine's headline. Two systems — **Nanite** (geometry) and **Lumen** (lighting) — change the content workflow fundamentally, and a third, **Virtual Shadow Maps**, ties them together. To use them well you need to know what each one *is* and what it costs.

### The Frame, in Brief

Unreal is a **deferred renderer** by default (with a forward path for VR/mobile). Deferred rendering means:

1. **G-Buffer pass:** render scene geometry once, writing surface data (albedo, normal, roughness, metallic, depth) into multiple full-screen buffers — not final color.
2. **Lighting pass:** for each light, read the G-Buffer and accumulate lighting. Decoupling geometry from lighting is what makes many dynamic lights affordable.
3. **Translucency, post-processing, tonemapping:** transparent surfaces (which deferred can't handle in the G-Buffer) are drawn forward; then bloom, depth of field, color grading, and the final tonemap.

Knowing it's deferred explains the costs you'll meet: many dynamic lights are cheap (deferred's strength), but transparency is expensive and overdraw-prone (deferred's weakness), and the G-Buffer eats memory bandwidth at high resolution.

### Nanite — Virtualized Geometry

Nanite is a **virtualized micropolygon geometry system**. The pitch: import film-quality meshes (millions of triangles) and Nanite streams and renders only the visible, screen-relevant detail — roughly a pixel-sized triangle budget regardless of source density. It replaces manual LOD authoring for static meshes.

How it changes the workflow:

- **No hand-authored LODs** for Nanite meshes — Nanite computes detail continuously.
- **Polycount stops being the primary budget** for opaque static geometry; Nanite's cost scales with screen pixels and instances, not source triangles.
- It works via a custom rasterizer and a per-cluster culling scheme; the GPU does fine-grained visibility on clusters of triangles.

Limits to know (they shift each version, but the shape holds): Nanite historically excelled at **opaque and masked static meshes**, with skeletal/deforming mesh and translucency support arriving and maturing over UE5.x releases. It has fixed overhead, so it's not automatically a win for simple scenes, and very small/instanced foliage has its own considerations. **Check the version's docs** rather than assuming — this is the fastest-moving part of the engine.

### Lumen — Dynamic Global Illumination

Lumen is **real-time global illumination and reflections**. GI means indirect light — light that bounces off surfaces and illuminates other surfaces (the soft fill light in a room lit by one window). Before Lumen, GI meant **baking**: precomputing static lighting into lightmaps, which forbade moving lights or geometry. Lumen does it dynamically, so you can move the sun, open a door and watch light spill in, and destroy walls, all with correct bounce lighting.

The tradeoff is cost and a quality/performance dial:

- Lumen uses a **software ray-tracing** path (via signed distance fields and a surface cache) that runs broadly, and a **hardware ray-tracing** path (via RT cores) for higher fidelity.
- It targets real-time framerates by being approximate — it's not path-traced ground truth, and it has resolution/noise characteristics you tune.
- It is the single biggest GPU cost in a typical UE5 scene. On lower-end or high-framerate targets, teams scale it down or fall back to baked lighting.

**The baked-vs-Lumen decision** is a real architectural choice: baked lighting is nearly free at runtime but static and requires lightmap UVs and bake times; Lumen is dynamic and workflow-friendly but expensive. Mobile and many competitive/high-FPS titles still bake.

### Virtual Shadow Maps (VSM)

VSM is the shadowing system designed to pair with Nanite and Lumen. It provides high-resolution, consistent shadows across a huge depth range by virtualizing the shadow map (allocating shadow resolution only where needed, like Nanite does for geometry). It's what makes Nanite's fine detail cast believable shadows. It also has a cost and caching behavior worth profiling.

### Materials, Lighting, and Post in One Picture

```
Meshes (Nanite or traditional) ─┐
Lights (dynamic) ───────────────┤
Materials (shaders) ────────────┼──► G-Buffer ──► Lumen GI + direct lighting
Sky / Environment ──────────────┘                    │
                                                      ▼
                            Translucency (forward) → Post-process stack →
                            (Bloom, DOF, Exposure, Color Grade, Tonemap) → Final image
```

### The Console Commands You'll Actually Use

```
stat fps          # framerate
stat unit         # frame time broken into Game / Draw / GPU / RHIT — the first triage
stat gpu          # GPU cost by pass (BasePass, Lumen, Shadows, ...)
r.Lumen.* / r.Nanite.*   # the cvars that scale these systems
showflag.* / viewmode    # visualize buffers (Lit, Unlit, Lighting Only, Overdraw, ...)
```

`stat unit` is the rendering triage tool: if **Game** is high you're CPU/gameplay-bound (look at Tick, Chapter 18); if **Draw** is high you have too many draw calls (batching, instancing); if **GPU** is high it's the renderer (Lumen, resolution, overdraw). Never optimize before `stat unit` tells you which one.

---

## 10. Materials

A material in Unreal is a **shader authored as a node graph**. The Material Editor is a visual front-end that compiles to HLSL shader code. Understanding the model — not just the nodes — lets you reason about cost and reuse.

### The Material Graph and the Output Node

Every material feeds a final node whose inputs are the **PBR (physically based rendering) surface properties**:

- **Base Color** — the albedo (the surface's color with no lighting).
- **Metallic** — 0 for non-metals (dielectrics), 1 for metals. Mostly binary in reality.
- **Roughness** — 0 = mirror-smooth, 1 = fully diffuse. The most expressive channel for "what is this surface."
- **Normal** — a normal map perturbing surface direction for fine detail without geometry.
- **Emissive** — light the surface emits (glowing screens, neon).
- **Specular**, **Ambient Occlusion**, **Opacity** (for translucent/masked), and others.

You build expressions feeding these inputs from textures, math nodes, and parameters. The same PBR inputs map directly onto the deferred G-Buffer from Chapter 9 — base color, normal, roughness, and metallic *are* what the G-Buffer stores.

### Shading Models and Blend Modes — The Two Big Switches

Two material settings dominate cost and behavior:

- **Blend Mode:** **Opaque** (writes depth, cheapest, deferred), **Masked** (opaque with a binary alpha cutout — foliage, chain-link, still deferred but with an alpha test), **Translucent** (real transparency — glass, water — rendered forward, expensive, depth-sorting issues, no deferred lighting niceties). Choosing Translucent when Masked would do is a common, costly mistake.
- **Shading Model:** Default Lit (standard PBR), Unlit (pure emissive, no lighting — UI, effects), Subsurface (skin, wax, foliage with light bleed), Clear Coat (car paint), and others. Each enables different inputs and costs.

### Material Instances — The Reuse Pattern

This is the single most important material concept for performance and workflow. A **Material** with **Parameters** (a `ScalarParameter` for roughness, a `VectorParameter` for color, a `TextureParameter` for the albedo map) becomes a *template*. A **Material Instance** overrides those parameters without recompiling the shader.

```
M_Metal  (the parent — compiled shader with parameters: Color, Roughness, Metallic)
├── MI_Gold      (instance: Color=gold, Roughness=0.2)
├── MI_RustyIron (instance: Color=brown, Roughness=0.8, + rust mask texture)
└── MI_Chrome    (instance: Color=white, Roughness=0.05)
```

Why it matters: **changing a Material Instance's parameter is nearly free** (no shader recompile), and instances can be changed at **runtime** via a `Dynamic Material Instance` (`CreateDynamicMaterialInstance` → `SetScalarParameterValue`) — that's how you make a health bar fill, a surface glow on hit, or a character flash red. Authoring 30 unique materials instead of one parameterized material with 30 instances multiplies shader compile time and breaks batching.

```cpp
// Runtime parameter change: flash the mesh red on damage.
UMaterialInstanceDynamic* MID =
    Mesh->CreateAndSetMaterialInstanceDynamic(0);
MID->SetVectorParameterValue(TEXT("EmissiveTint"), FLinearColor::Red);
```

### Material Cost — What to Watch

Shader cost is roughly the instruction count and texture-sample count, multiplied by how many pixels the material covers (and overdraw for translucency). The `Stats` panel in the Material Editor shows the instruction count. Translucent overdraw (many transparent layers stacking on the same pixels) is a frequent GPU killer — the `Shader Complexity` view mode visualizes it (green = cheap, red = expensive).

---

## 11. Animation

Unreal's animation system is deep; this chapter builds the spine: how a skeleton drives a mesh, how an Animation Blueprint chooses and blends poses, and the constructs (state machines, blend spaces, montages) you'll use daily.

### The Data Model

```
Skeleton (the bone hierarchy + reference pose)  ── shared across compatible meshes
   │
Skeletal Mesh (the rendered geometry, skinned to the skeleton)
   │
Animation Sequences (clips: walk, run, jump) ── authored against the Skeleton
   │
Animation Blueprint (the per-frame logic that picks/blends poses → final pose)
```

The crucial decoupling: **animations target a Skeleton, not a specific mesh.** Any skeletal mesh sharing that skeleton can play the same animations — so a roster of characters with the same rig shares one animation library. This is why "retargeting" (Chapter end) exists for *different* skeletons.

### The Animation Blueprint — Two Graphs

An Animation Blueprint (AnimBP) has two cooperating graphs:

1. **Event Graph (the "think" side):** runs game-thread logic to compute variables — speed, direction, is-falling, is-aiming. Typically a `BlueprintUpdateAnimation` (or the threaded `BlueprintThreadSafeUpdateAnimation`) reads the owning Pawn's state into AnimBP variables every frame.
2. **AnimGraph (the "pose" side):** a node graph that *produces a pose*. It reads the variables from the event graph and flows poses through state machines, blend nodes, and modifiers into the final `Output Pose`.

The separation mirrors the rest of the engine: gather data, then transform it into output.

### State Machines

The AnimGraph's backbone for locomotion. States are poses or sub-graphs (Idle, Walk, Run, Jump, Fall); transitions are rules (booleans/conditions) that move between them with blend times.

```
        [Idle/Walk/Run] ── Speed → 0 ───► (stays)
              │  Jump pressed
              ▼
           [Jump Start] ──auto──► [In Air] ──IsFalling=false──► [Land] ──► [Idle/Walk/Run]
```

Transition rules read the AnimBP variables ("Speed > 0", "IsInAir"). Blend times on transitions prevent pops. A single "Locomotion" state often contains a **Blend Space** rather than discrete walk/run states.

### Blend Spaces

A Blend Space maps **continuous input(s) to a blended pose**. A 1D blend space blends idle→walk→run along a Speed axis; a 2D blend space blends by Speed *and* Direction so a character leans into strafes. You place sample animations at coordinates and the engine interpolates between the nearest samples. This is how smooth, analog locomotion replaces hard state switches.

### Montages — Playing One-Shots Over Locomotion

Animation Montages play *authored, interruptible sequences* on top of the state machine — an attack swing, a reload, a hit reaction. They support:

- **Sections** (named segments you can jump between — combo chains).
- **Notifies** — events fired at specific frames: "play footstep sound here," "enable weapon collision now," "spawn this effect." Notifies are how animation drives gameplay timing (the sword only damages during the swing's active frames).
- **Slots** — the AnimGraph has a `Slot` node where montages inject their pose, blending over the base locomotion (upper body reloads while legs keep running).

```cpp
// Play an attack montage from C++; bind to its end.
float Duration = AnimInstance->Montage_Play(AttackMontage);
FOnMontageEnded EndDelegate;
EndDelegate.BindUObject(this, &AHero::OnAttackEnded);
AnimInstance->Montage_SetEndDelegate(EndDelegate, AttackMontage);
```

### Beyond the Basics

- **Control Rig** — in-engine procedural rigging and animation (IK, foot placement on uneven ground, procedural tails) driven by a graph; increasingly the home for runtime adjustments.
- **IK (Inverse Kinematics)** — foot IK keeps feet on slopes/stairs; hand IK aligns hands to weapons. UE5's **IK Rig** and **IK Retargeter** standardize this and handle retargeting animations between different skeletons.
- **Layered blending / additive animations** — aim offsets (looking up/down) layered additively over locomotion.

---

## 12. Physics & Collision

Unreal's physics runs on **Chaos**, Epic's in-house physics engine (which replaced PhysX in UE5). You'll interact with it through collision settings far more than through raw simulation, so the collision model is the priority.

### Collision Is Channel-Based

Every collidable component has a **Collision Response** configuration answering, for each **channel**, "do I Ignore, Overlap, or Block it?"

- **Object Type** — what this component *is* (WorldStatic, WorldDynamic, Pawn, PhysicsBody, Vehicle, or custom channels you define).
- **Response to each channel** — Ignore / Overlap / Block.

The interaction between two objects is the *intersection* of their responses: a hit/overlap occurs based on what *both* say. Two objects **Block** each other → a physical collision (and a `Hit` event). One **Overlaps** → they pass through but fire **Overlap** events (triggers, pickups). Either **Ignores** → nothing.

```
Trigger Volume:  Object Type = WorldStatic,  Response to Pawn = Overlap
Player Capsule:  Object Type = Pawn,         Response to WorldStatic = Block
                 → but trigger says Overlap, so net result = OVERLAP
                 → OnComponentBeginOverlap fires; player walks through
```

**Collision Presets** (BlockAll, OverlapAllDynamic, Pawn, Trigger, etc.) are named bundles of these responses — use them instead of hand-setting every channel. Custom channels (Project Settings → Collision) let you express game-specific interactions ("Bullets block walls and enemies but ignore other bullets").

### The Two Event Types

```cpp
// Overlap: things passing through trigger this (pickups, zones).
MyTrigger->OnComponentBeginOverlap.AddDynamic(this, &AMyActor::OnOverlap);

void AMyActor::OnOverlap(UPrimitiveComponent* Overlapped, AActor* Other,
    UPrimitiveComponent* OtherComp, int32 BodyIndex, bool bFromSweep,
    const FHitResult& Sweep) { /* ... */ }

// Hit: blocking collisions trigger this (impacts, landing).
MyMesh->OnComponentHit.AddDynamic(this, &AMyActor::OnHit);
```

`OnComponentBeginOverlap`/`EndOverlap` need "Generate Overlap Events" enabled. `OnHit` needs "Simulation Generates Hit Events" and a blocking response. Forgetting these flags is the #1 reason "my collision callback doesn't fire."

### Traces (Raycasts) — The Workhorse of Gameplay

Most "did the gun hit something" / "is there ground below" / "what am I looking at" logic uses **traces**, not simulated physics:

```cpp
FHitResult Hit;
FVector Start = Muzzle->GetComponentLocation();
FVector End   = Start + (AimDirection * 10000.f);
FCollisionQueryParams Params;
Params.AddIgnoredActor(this);   // don't shoot yourself

bool bHit = GetWorld()->LineTraceSingleByChannel(
    Hit, Start, End, ECC_Visibility, Params);

if (bHit)
{
    AActor* HitActor = Hit.GetActor();
    FVector ImpactPoint = Hit.ImpactPoint;
    FVector ImpactNormal = Hit.ImpactNormal;   // for decals/effects
    // apply damage, spawn impact FX...
}
```

Variants: `LineTraceSingle/Multi` (by channel or object type), `SweepSingle` (a shape swept along a path — for "can this capsule fit"), and the `...ByObjectType` family. Traces are cheap and deterministic, which is why hitscan weapons, line-of-sight checks, and ground detection all use them rather than spawning physics bodies.

### Simulated Physics

For objects that should tumble, fall, and respond to forces, enable **Simulate Physics** on a primitive component. It then has mass, responds to gravity and impulses (`AddImpulse`, `AddForce`), and resolves collisions with other physics bodies. Specialized systems build on Chaos: **physics constraints** (joints/hinges/ragdolls), **Chaos Vehicles**, **Chaos Cloth**, and **Chaos Destruction** (Geometry Collections fracturing into pieces). Simulated physics is more expensive than traces and is non-deterministic across machines — important for networking (Chapter 16), where you usually don't replicate raw physics but instead replicate results.

### Character Movement Is Not Raw Physics

`UCharacterMovementComponent` (on every `Character`) does **not** use simulated rigid-body physics for walking. It's a custom, network-friendly kinematic mover that handles walking, stepping up stairs, slope limits, jumping, falling, swimming, and crouching — with built-in client prediction and server reconciliation for multiplayer. This is why you configure walk speed and jump height as properties rather than applying forces. Reach for simulated physics for ragdolls and props, not for the player's normal locomotion.

---

## 13. Input

Modern Unreal uses the **Enhanced Input** system (the default since UE5; the legacy "Action/Axis Mappings" are deprecated). It's a data-driven, context-aware input layer that's worth learning correctly from the start.

### The Three Concepts

1. **Input Action (IA)** — an abstract intent: "Jump," "Move," "Fire." It has a value type (boolean, 1D axis, 2D axis like a stick/WASD vector, 3D). Gameplay code binds to the *Action*, not to a key — so it never cares whether Jump came from spacebar or a gamepad button.
2. **Input Mapping Context (IMC)** — a set of bindings from physical inputs (keys, buttons, axes) to Actions, with **Modifiers** and **Triggers**. You can push/pop multiple contexts with priorities — a "driving" context overrides the "on-foot" context when you enter a vehicle, then pops when you exit.
3. **Modifiers and Triggers** — Modifiers transform raw input (negate, swizzle XY→YX, dead zone, scale); Triggers decide *when* an Action fires (Pressed, Released, Hold for 0.5s, Tap, Pulse). "Hold E to revive" is a Hold trigger, no timer code needed.

```
Spacebar ─┐
Gamepad A ─┼──[IMC_OnFoot]──► IA_Jump (bool) ──► bound C++/BP handler → Character->Jump()
          │
W/A/S/D ──┴──[IMC_OnFoot]──► IA_Move (Vector2D, with negate/swizzle modifiers)
```

### Wiring It Up in C++

```cpp
void AHero::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
    // Add the mapping context (usually in BeginPlay via the local player subsystem).
    if (APlayerController* PC = Cast<APlayerController>(Controller))
    {
        auto* Subsys = ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(
            PC->GetLocalPlayer());
        Subsys->AddMappingContext(OnFootContext, /*Priority=*/0);
    }

    auto* EIC = CastChecked<UEnhancedInputComponent>(PlayerInputComponent);
    EIC->BindAction(JumpAction, ETriggerEvent::Started,   this, &AHero::OnJump);
    EIC->BindAction(MoveAction, ETriggerEvent::Triggered, this, &AHero::OnMove);
}

void AHero::OnMove(const FInputActionValue& Value)
{
    const FVector2D Axis = Value.Get<FVector2D>();   // typed by the IA's value type
    AddMovementInput(GetActorForwardVector(), Axis.Y);
    AddMovementInput(GetActorRightVector(),   Axis.X);
}
```

`IA_*` and `IMC_*` assets are created in the editor and assigned to the C++ class as `UPROPERTY` references — the classic data-driven split: C++ binds the *Action*, designers configure *which keys* in the IMC.

---

## 14. UI — UMG & Slate

Unreal has two UI layers. **Slate** is the C++ framework the entire editor is built in — verbose, powerful, code-only. **UMG (Unreal Motion Graphics)** is the designer-facing layer built on Slate: you compose widgets visually in the **Widget Blueprint** editor. For game UI, you use UMG; you drop to Slate only for editor tooling or extreme cases.

### The UMG Model

A **Widget Blueprint** (a `UUserWidget` subclass) has two parts, mirroring the AnimBP split:

- **Designer view** — a visual canvas where you place widgets (Text, Button, Image, ProgressBar, etc.) into a layout hierarchy.
- **Graph view** — a Blueprint (or C++) graph for behavior: button click handlers, binding values, animations.

```
UUserWidget (your HUD)
├── CanvasPanel (free positioning) / Overlay / Horizontal/VerticalBox (auto-layout)
│   ├── ProgressBar  "HealthBar"   (bound to Health/MaxHealth)
│   ├── TextBlock    "AmmoText"    (bound to a function returning ammo string)
│   └── Button       "PauseButton" (OnClicked → open pause menu)
```

### Layout — Slots and Containers

Layout is hierarchical: each child sits in a **Slot** whose type depends on the parent panel. A `CanvasPanel` slot has anchors and absolute positions (for HUDs pinned to screen corners); a `HorizontalBox` slot has fill/size rules (for auto-arranged rows). **Anchors** are the key to resolution independence — anchoring a health bar to the bottom-left corner keeps it there on any screen size. Mixing up "I want this pinned to a corner" (CanvasPanel + anchor) with "I want these laid out in a row" (HorizontalBox) is the usual beginner layout confusion.

### Getting Data Into the UI — Three Ways

1. **Property Binding** (a function the widget polls every frame) — easy but runs every frame; fine for a few values, wasteful at scale.
2. **Event-driven updates** (the right default) — the game broadcasts a delegate ("HealthChanged") and the widget updates only then. No per-frame polling. This is the Chapter 5 Event Dispatcher pattern applied to UI.
3. **MVVM (Model-View-ViewModel)** — UE5's structured approach (the UMG ViewModel plugin): a ViewModel object holds UI state, the view binds to it, and changes propagate automatically. The scalable choice for complex UIs.

```cpp
// Create and show a HUD widget from the PlayerController.
UUserWidget* HUD = CreateWidget<UUserWidget>(PlayerController, HUDWidgetClass);
HUD->AddToViewport();

// Event-driven update: subscribe to the character's delegate.
MyCharacter->OnHealthChanged.AddDynamic(HUDWidget, &UHUDWidget::UpdateHealth);
```

### Performance Notes

Per-frame property bindings and deep widget hierarchies are the usual UMG costs; `Invalidation Boxes` cache widgets that don't change often, and the **Widget Reflector** (an editor tool) inspects the live widget tree. Heavy 3D-in-UI (render targets, retainer boxes) is powerful but expensive.

---

## 15. Audio

Modern Unreal audio centers on **MetaSounds**, a node-based audio system that is effectively "Blueprint for DSP" — you build the actual sound-generating signal graph, sample by sample, with full procedural control. Alongside it sits the **submix** mixing graph and **attenuation/spatialization** for 3D sound.

### The Pieces

- **Sound Wave** — an imported audio file (the raw asset).
- **MetaSound Source** — a procedural sound graph: oscillators, samplers, filters, envelopes, randomization, and inputs you can drive from gameplay (pitch by speed, filter by health). It replaces the older Sound Cue for new work, offering true synthesis and per-instance parameter control.
- **Attenuation Settings** — how a sound fades with distance, its spatialization (stereo→3D positioning, occlusion, falloff curves). This is what makes a sound feel located in the world.
- **Submixes** — a routing/mixing graph. Sounds route into submixes (SFX, Music, Voice, Master), where you apply effects (reverb, EQ, compression) and control group volume — exactly how a mixing console's buses work. The classic use: a "duck music when dialogue plays" sidechain on the music submix.
- **Sound Classes / Mixes** — categorize sounds and apply volume/effect passes (the player's Music/SFX/Voice sliders map to Sound Classes).

```
MetaSound Source (footstep: sampler + random pitch + surface-type input)
        │  played at a location with Attenuation
        ▼
   SFX Submix ──► Master Submix ──► output
Music Source ──► Music Submix ─┘   (ducked when Voice Submix is active)
```

### Playing Sound From Code

```cpp
// 2D / non-spatial (UI click, music):
UGameplayStatics::PlaySound2D(this, ClickSound);

// 3D / positional (fades with distance, uses attenuation):
UGameplayStatics::PlaySoundAtLocation(this, ExplosionSound, ImpactLocation);

// Attached, controllable instance (engine loop that follows a car, with live params):
UAudioComponent* Engine = UGameplayStatics::SpawnSoundAttached(
    EngineSound, CarMesh);
Engine->SetFloatParameter(TEXT("RPM"), CurrentRPM);  // drives the MetaSound graph
```

The `UAudioComponent` (a spawned, attached instance) is what you keep a handle to when a sound must follow an object and respond to gameplay (RPM, intensity) live — that's the MetaSound parameter system in action.

---

## 16. Networking & Replication

Unreal has one of the most battle-tested multiplayer architectures in the industry, and it's also where the gameplay framework (Chapter 4) pays off. The model is **server-authoritative client-server with a single shared codebase** — the same C++/Blueprint runs as server or client, and `if (HasAuthority())` checks branch behavior.

### The Authority Model

```
                 ┌──────────── SERVER (authority) ────────────┐
                 │  Owns truth: GameMode, real Actor state,    │
                 │  hit registration, score. Replicates DOWN.  │
                 └───────────────┬─────────────────────────────┘
                      replication │ (state) + RPCs
                 ┌────────────────┴───────────────┐
            ┌────▼─────┐                      ┌────▼─────┐
            │ Client A │  sends input/requests│ Client B │
            │ (a copy) │  UP via Server RPCs  │ (a copy) │
            └──────────┘                      └──────────┘
```

The cardinal rule: **the server is authoritative.** Clients never directly change important state; they *ask* the server (via a Server RPC), the server validates and applies it, then the new state *replicates* back down to all clients. This is the anti-cheat foundation — a hacked client can lie about its input, but it can't change the score, because the score lives on the server. The `GameMode` existing only on the server (Chapter 4) is this rule made structural.

### Roles and the `HasAuthority` Check

Every Actor has a role telling it where it "really" lives:

- **`ROLE_Authority`** — the authoritative copy (on the server, or the actor's owning client for client-authoritative cases).
- **`ROLE_SimulatedProxy`** — a replicated copy on a client, driven by data from the server (other players' characters you see).
- **`ROLE_AutonomousProxy`** — the local player's own pawn on their client, which does prediction.

```cpp
if (HasAuthority())   // true on the server (and single-player)
{
    // Safe to change authoritative state here.
    Health -= Damage;
}
```

### Property Replication

Mark a `UPROPERTY` as `Replicated` and the engine syncs it from server to clients automatically (built on reflection, Chapter 8). You declare which properties replicate in `GetLifetimeReplicatedProps`:

```cpp
UPROPERTY(ReplicatedUsing = OnRep_Health)   // calls OnRep_Health on clients when it changes
float Health;

UPROPERTY(Replicated)
int32 Ammo;

void AMyChar::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const
{
    Super::GetLifetimeReplicatedProps(Out);
    DOREPLIFETIME(AMyChar, Health);
    DOREPLIFETIME(AMyChar, Ammo);
}

UFUNCTION()
void AMyChar::OnRep_Health()   // runs on clients after Health replicates
{
    UpdateHealthBar();         // react to the change (e.g., update UI, play hit FX)
}
```

`ReplicatedUsing` (a **RepNotify**) is the key idiom: the server changes the value, it replicates, and each client runs `OnRep_*` to *react* (update the health bar, play a hit flash). Replication only flows **server → client**; properties are not auto-synced upward.

### RPCs — Remote Procedure Calls

Three flavors, set by `UFUNCTION` specifiers:

```cpp
// Client → Server: "please do this for me" (validated server-side).
UFUNCTION(Server, Reliable, WithValidation)
void Server_Fire(FVector_NetQuantize Target);

// Server → owning client only.
UFUNCTION(Client, Reliable)
void Client_ShowHitMarker();

// Server → ALL clients (explosions, sounds everyone should see).
UFUNCTION(NetMulticast, Unreliable)
void Multicast_PlayExplosionFX(FVector Location);
```

- **`Server`** RPCs are how clients request authoritative actions ("I fired"). Always `WithValidation` to reject cheats.
- **`Client`** RPCs target the one owning client.
- **`NetMulticast`** RPCs run on the server and all clients — for cosmetic events everyone needs (FX, sounds).
- **`Reliable`** guarantees delivery (use sparingly — it can clog the channel); **`Unreliable`** is fire-and-forget (fine for frequent cosmetic events).

### Prediction and the Feel of Multiplayer

If every action waited for a server round-trip, movement would feel laggy. `UCharacterMovementComponent` solves this with **client-side prediction**: your client moves your character *immediately* and simultaneously sends the input to the server. The server simulates authoritatively and sends back the correct position; if the client predicted wrong (it diverged), it gets **corrected** (reconciled), causing the occasional rubber-band. Other players' characters are smoothed via **interpolation** between received updates. You get this for free with `Character`, which is a major reason to build on it.

### What to Replicate — The Bandwidth Discipline

Replicate **decisions and results, not raw streams.** Don't replicate physics simulation tick-by-tick; replicate "the door is now open" and let each client animate it. Use **relevancy** (the server skips replicating actors a client can't see) and **net update frequency** to control cost. Bandwidth is the budget; reflection makes replication easy, but easy isn't free.

---

## 17. Assets, Cooking & Packaging

Shipping a game means turning the editor's `.uasset` files into a platform-optimized package. The pipeline has its own vocabulary.

### How Assets Reference Each Other

Assets form a **reference graph**: a level references the meshes it places, each mesh references its materials, each material references its textures. The engine tracks this graph (the **Asset Registry**), which powers the **Reference Viewer** (right-click an asset → Reference Viewer) — indispensable for answering "why is this 200 MB asset in my build?" and "what breaks if I delete this?"

This graph is also the memory story from Chapter 8: a hard reference pulls the whole subtree into memory together. The Size Map tool visualizes the memory footprint of an asset and everything it hard-references.

### Cooking

**Cooking** converts editor assets into runtime-ready, platform-specific formats:

- Textures are compressed to the platform's GPU format (BC on desktop, ASTC on mobile).
- Shaders are compiled for the target's graphics API.
- Editor-only data is stripped.
- Assets are serialized into an optimized form.

Cooked content can't be opened in the editor — it's the runtime artifact. The **Derived Data Cache (DDC)** caches these expensive conversions (especially shader compilation) so they're not redone every cook; a shared network DDC dramatically speeds up a team's iteration.

### Packaging

Packaging cooks the content, compiles your game's code for the target configuration, and assembles a runnable build. Build **configurations** matter:

- **Debug / DebugGame** — full debug info, slow; for stepping through code.
- **Development** — optimized but with logging, `stat` commands, and the console; your daily build.
- **Shipping** — fully optimized, logging and debug commands stripped; what ships to players. **Always test a Shipping build before release** — `check`/`ensure` behavior, logging, and PIE-only assumptions (Chapter 2) differ.

### Pak Files and Asset Loading at Runtime

Cooked assets are bundled into **`.pak`** files (optionally compressed/encrypted). At runtime, the engine streams from them. For DLC, patches, and large games, **chunking** and **Asset Manager** (with **Primary Asset Ids** and **Asset Bundles**) let you load/unload content on demand and ship updates without re-downloading everything. This is where soft references (Chapter 8) pay off: a soft-referenced boss can live in its own chunk, downloaded only when reached.

---

## 18. Performance & Profiling

Performance work in Unreal follows one discipline: **measure, find the bottleneck, fix that, re-measure.** The engine gives you exceptional tools; the failure mode is optimizing by guesswork. Recall from Chapter 9 that the frame splits across Game (CPU gameplay), Draw (CPU render submission), and GPU.

### The Triage Ladder

```
1. stat unit           → which of Game / Draw / GPU is the bottleneck?
2. stat fps            → confirm the framerate problem is real and reproducible
3. Then, per culprit:
     Game high  → stat game, Unreal Insights (CPU), look at Tick
     Draw high  → stat scenerendering, draw call count, batching/instancing
     GPU  high  → stat gpu, GPU Visualizer (ProfileGPU), Lumen/shadow/overdraw cost
```

`stat unit` is non-negotiable as step one. Optimizing GPU when you're CPU-bound (or vice versa) wastes effort and can even make things worse.

### Unreal Insights — The Real Profiler

`stat` commands are triage; **Unreal Insights** is the deep profiler. It captures a timeline trace (CPU timing per function/frame, GPU, memory allocations, networking, Slate, file I/O, loading) that you analyze offline. It's how you find the specific function eating your Game thread, the asset load stalling a frame, or the allocation spike. Launch with tracing enabled (`-trace=cpu,gpu,frame` or the toolbar) and open the `.utrace` in the Insights app.

### The Usual CPU Culprits

- **Tick abuse** (Chapter 3) — hundreds of Actors ticking. Fix: disable ticks, use events/timers, tick less often.
- **Blueprint in hot paths** (Chapter 5) — heavy per-frame BP graphs. Fix: move to C++.
- **Excessive casts / `GetAllActorsOfClass`** — the latter iterates every actor in the world; never per-frame. Fix: cache references, use a manager/subsystem, or tag-based lookup.
- **Synchronous asset loads** — loading a hard-referenced asset mid-gameplay hitches the frame. Fix: async load soft references ahead of need.
- **Overlap event spam** — many overlapping volumes generating events. Fix: tighten collision responses (Chapter 12).

### The Usual GPU Culprits

- **Overdraw**, especially translucent materials stacking (Chapter 10). Fix: prefer Masked over Translucent, reduce particle layering; check with the Shader Complexity view.
- **Lumen and Virtual Shadow Map cost** (Chapter 9) — the biggest dynamic GPU expense. Fix: scale Lumen quality cvars, consider baked lighting on constrained targets.
- **Too many draw calls** — each unique mesh+material is a draw call. Fix: instancing (`InstancedStaticMesh`/`HierarchicalISM`), merging static meshes, fewer unique materials (Material Instances, Chapter 10).
- **Resolution / post-process** — at 4K everything costs more; dynamic resolution and temporal upscaling (TSR — Temporal Super Resolution) are the standard levers.
- **High-poly non-Nanite meshes** without LODs. Fix: Nanite for static meshes, or author LODs.

### Memory

The **Size Map** and **Reference Viewer** (Chapter 17) show what's resident and why. `stat memory`/`memreport` and Insights' memory track find leaks and bloat. The recurring theme from Chapter 8 returns: hard references determine your memory footprint; soft references and the Asset Manager are how you control it.

### The One Habit

Build a **Development** configuration, run on **target hardware** (not your dev rig), capture an **Insights** trace, and read `stat unit` first. Every other technique is downstream of knowing which thread is the bottleneck. Profiling on a beefy workstation hides the problems your players will hit.

---

## 19. Patterns & Recipes

### Recipe: A Pickup Item (Overlap → Effect → Destroy)

The canonical first gameplay loop, tying together components, overlap events, and lifecycle.

```cpp
APickup::APickup()
{
    Sphere = CreateDefaultSubobject<USphereComponent>(TEXT("Sphere"));
    RootComponent = Sphere;
    Sphere->SetCollisionProfileName(TEXT("Trigger"));  // overlap pawns, block nothing

    Mesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Mesh"));
    Mesh->SetupAttachment(Sphere);
    Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}

void APickup::BeginPlay()
{
    Super::BeginPlay();
    Sphere->OnComponentBeginOverlap.AddDynamic(this, &APickup::OnOverlap);
}

void APickup::OnOverlap(UPrimitiveComponent*, AActor* Other, UPrimitiveComponent*,
    int32, bool, const FHitResult&)
{
    if (!HasAuthority()) return;          // server decides who picks up (Chapter 16)
    if (auto* Char = Cast<AMyCharacter>(Other))
    {
        Char->GrantItem(ItemData);
        Multicast_PlayPickupFX(GetActorLocation());  // cosmetic, all clients
        Destroy();                         // server destroys; replicates to clients
    }
}
```

### Recipe: A Component You Reuse Across Actors (Health)

The composition pattern — drop this on any Actor that can take damage.

```cpp
UCLASS(ClassGroup=(Gameplay), meta=(BlueprintSpawnableComponent))
class UHealthComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Health")
    float MaxHealth = 100.f;

    UPROPERTY(ReplicatedUsing=OnRep_Health, BlueprintReadOnly, Category="Health")
    float Health;

    // Broadcast so UI/AI/anything reacts without HealthComponent knowing them.
    UPROPERTY(BlueprintAssignable)
    FOnHealthChanged OnHealthChanged;

    void ApplyDamage(float Amount);   // server-authoritative
protected:
    virtual void BeginPlay() override { Super::BeginPlay(); Health = MaxHealth; }
    UFUNCTION() void OnRep_Health() { OnHealthChanged.Broadcast(Health, MaxHealth); }
};
```

Any Actor adds this component; the UI subscribes to `OnHealthChanged` (Chapter 14); the server owns the value and replicates it (Chapter 16). One component, zero coupling.

### Recipe: Subsystems Instead of Singletons

Need a manager (audio director, save system, match flow) accessible from anywhere without a global? Use a **Subsystem** — an engine-managed singleton with a defined lifetime and automatic creation. No manual instantiation, no GC worries, no `static` footguns.

```cpp
UCLASS()
class USaveSubsystem : public UGameInstanceSubsystem  // lives as long as the game
{
    GENERATED_BODY()
public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    UFUNCTION(BlueprintCallable) void SaveGame();
};

// Anywhere:
auto* Save = GetGameInstance()->GetSubsystem<USaveSubsystem>();
```

Subsystem flavors map to lifetimes: `UGameInstanceSubsystem` (whole game), `UWorldSubsystem` (per level), `ULocalPlayerSubsystem` (per local player — used by Enhanced Input, Chapter 13), `UEngineSubsystem` (editor+runtime). This is the modern, GC-safe replacement for the global-manager pattern.

### Recipe: Data-Driven Design with DataAssets and DataTables

Stop hardcoding gameplay numbers in C++.

- **`UDataAsset`** (and `UPrimaryDataAsset`) — a designer-authored asset holding configuration: a weapon's stats, an enemy's parameters, an item definition. Soft-reference it and load on demand.
- **`UDataTable`** — a spreadsheet (importable from CSV/JSON) of rows of a struct: all 200 items, all enemy stat lines. Look up by row name at runtime.

This pushes balance and content out of code into assets designers own — the same C++/content division that runs through the whole engine.

### The "C++ Base, Blueprint Derived" Template (the meta-pattern)

Every recipe above embodies the engine's central pattern, worth stating once more as the through-line:

1. **C++** owns correctness, performance, and networking: the math, the authoritative state, the replication.
2. **Blueprint subclasses** own content and feel: which mesh/sound/FX, the exact numbers, the visual polish.
3. **The seam** is `UPROPERTY(EditAnywhere)` for tunables, `BlueprintImplementableEvent` for designer hooks, and `TSubclassOf` for "pick which class."
4. **Communication** is event dispatchers/delegates for decoupling, interfaces for cross-type calls, subsystems for shared services.

Internalize this and Unreal stops being a pile of features and becomes a coherent system.

---

## 20. Mastery Checklist

### Foundations
- [ ] Explain the four layers (core → subsystems → framework → your game) and why reflection underlies GC, serialization, the editor, Blueprint, and networking
- [ ] State the Blueprint-vs-C++ tradeoff and the "C++ base, Blueprint derived" pattern from memory
- [ ] Navigate a project on disk: know what's source-of-truth vs generated, and why `Content/` is unmergeable
- [ ] Use `stat fps`, `stat unit`, and the console; read `stat unit` to identify Game/Draw/GPU bottlenecks

### Object Model & Framework
- [ ] Distinguish `UActorComponent` / `USceneComponent` / `UPrimitiveComponent` and explain root components and attachment
- [ ] Order the Actor lifecycle (constructor → `PostInitializeComponents` → `BeginPlay` → `Tick` → `EndPlay`) and know what's safe where
- [ ] Explain why a Controller possesses a Pawn, and what GameMode / GameState / PlayerState / PlayerController each own
- [ ] Justify avoiding `Tick`; replace a polling tick with an event or timer

### C++ & Reflection
- [ ] Write a `UCLASS` with `GENERATED_BODY`, `UPROPERTY`, and `UFUNCTION` correctly, including the `.generated.h` include
- [ ] Explain the two memory worlds and why a `UObject*` without `UPROPERTY` is a use-after-free
- [ ] Choose correctly among `FString` / `FName` / `FText`, and `TObjectPtr` / `TWeakObjectPtr` / `TSubclassOf`
- [ ] Describe what UHT does and why the macros are markers for code generation
- [ ] Expose C++ to Blueprint and call Blueprint from C++ (`BlueprintImplementableEvent` vs `BlueprintNativeEvent`)

### Rendering, Materials, Animation
- [ ] Explain deferred rendering, the G-Buffer, and why transparency is the expensive case
- [ ] Describe what Nanite, Lumen, and Virtual Shadow Maps each do and their main costs; argue baked-vs-Lumen for a target
- [ ] Build a parameterized Material and create runtime Material Instances; explain why instances beat unique materials
- [ ] Diagram an Animation Blueprint's two graphs and explain state machines, blend spaces, and montage notifies

### Systems
- [ ] Configure channel-based collision (Object Type + responses) and explain Overlap vs Hit and their required flags
- [ ] Use a line trace for hitscan/line-of-sight and explain why character movement isn't raw physics
- [ ] Set up Enhanced Input (Input Action + Mapping Context + Triggers/Modifiers)
- [ ] Build a UMG HUD updated by an event dispatcher rather than per-frame binding
- [ ] Explain MetaSounds, attenuation, and submixes

### Networking & Shipping
- [ ] Explain server authority, `HasAuthority`, and the three actor roles
- [ ] Replicate a property with `ReplicatedUsing`/`GetLifetimeReplicatedProps` and use a RepNotify to react
- [ ] Choose among Server / Client / NetMulticast RPCs and Reliable vs Unreliable
- [ ] Explain client prediction and reconciliation in `CharacterMovementComponent`
- [ ] Describe cooking, build configurations, and why you must test a Shipping build
- [ ] Use the Reference Viewer / Size Map and soft references to control memory; capture and read an Unreal Insights trace

---

## 21. Additional Resources

A curated reading list for newcomers. Start with the engine-agnostic foundations if you're new to game development entirely — the concepts (game loop, vectors, frame timing, scene graphs) transfer to *any* engine and make Unreal far less mysterious. Then move to the Unreal-specific material.

### Game development fundamentals (engine-agnostic)

These build the mental model behind *every* engine, so the knowledge survives switching tools.

- **[Game Programming Patterns](https://gameprogrammingpatterns.com/)** by Robert Nystrom — free to read online. The single best book for understanding *why* engines are built the way they are: the game loop, update method, component pattern, object pools, state machines. Reading this makes Unreal's Actor/Component/Tick model feel inevitable rather than arbitrary.
- **[The Nature of Code](https://natureofcode.com/)** by Daniel Shiffman — free online. Vectors, forces, oscillation, and simulation explained from scratch with intuition first. The foundation for understanding movement, physics, and `DeltaTime`.
- **[Game Engine Architecture](https://www.gameenginebook.com/)** by Jason Gregory — the definitive deep reference on how commercial engines (the author works on Naughty Dog's) are structured: subsystems, memory, rendering, animation, gameplay. Dense; treat it as a reference to grow into, not a first read.
- **[Catlike Coding](https://catlikecoding.com/)** — Unity-focused, but the tutorials on meshes, shaders, and math are some of the clearest explanations of 3D rendering concepts anywhere, and the ideas port directly to Unreal's Material Editor and rendering model.
- **[Learn OpenGL](https://learnopengl.com/)** — if you want to understand what's happening *beneath* the renderer (the pipeline, shaders, lighting, the G-buffer this guide references in Chapter 9). Pairs with this repo's [WebGL/OpenGL guide](WEBGL_OPENGL_STUDY_GUIDE.md).
- **[3Blue1Brown — Linear Algebra](https://www.3blue1brown.com/topics/linear-algebra)** — vectors, matrices, and transforms with visual intuition. The math under every camera, bone, and transform in any engine.

### Official Unreal Engine resources (start here for Unreal)

- **[Epic Developer Community Learning](https://dev.epicgames.com/community/unreal-engine/learning)** — Epic's free official courses and tutorials, from "Your First Hour in Unreal Engine" through gameplay, Blueprints, materials, and rendering. The authoritative starting point.
- **[Unreal Engine Documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine)** — the official docs, organized by system. Use it as a reference alongside this guide.
- **[Unreal Engine C++ API Reference](https://dev.epicgames.com/documentation/en-us/unreal-engine/API)** — the searchable API for every `UCLASS`, function, and component when you're writing C++.
- **[Unreal Engine YouTube channel](https://www.youtube.com/@UnrealEngine)** — official feature overviews, livestreams, and "Inside Unreal" deep dives.
- **[Unreal Source on GitHub](https://github.com/EpicGames/UnrealEngine)** — the full engine source (requires linking your Epic and GitHub accounts). The ultimate reference: when docs are thin, read how the engine does it. Pair with the [Lyra sample game](https://dev.epicgames.com/documentation/en-us/unreal-engine/lyra-sample-game-in-unreal-engine), Epic's production-quality reference project.

### Beginner-friendly Unreal courses and channels

- **[Tom Looman's Unreal Engine C++ course & blog](https://www.tomlooman.com/)** — Tom is a former Epic engineer; his free articles and (paid) "Professional Game Development in C++ and Unreal Engine" course are the standard recommendation for learning Unreal C++ the right way, with the C++/Blueprint split this guide emphasizes.
- **[GameDev.tv Unreal courses](https://www.gamedev.tv/)** — beginner-oriented, project-based courses (often bundled on Udemy) that walk you from zero to a finished small game. Good if you learn best by building.
- **[Ben Cloward (materials & shaders)](https://www.youtube.com/@BenCloward)** — the go-to channel for the Material Editor (Chapter 10) and shader concepts, explained clearly and applicable to other engines too.
- **[Mathew Wadstein (WTF Is...?)](https://www.youtube.com/@MathewWadsteinTutorials)** — a huge library of short "what does this single node/function do" videos. Excellent as a just-in-time reference when you hit an unfamiliar Blueprint node.

### Community and staying current

- **[Unreal Engine forums](https://forums.unrealengine.com/)** and **[r/unrealengine](https://www.reddit.com/r/unrealengine/)** — for questions, troubleshooting, and seeing what others build.
- **[Unreal Slackers Discord](https://unrealslackers.org/)** — a large, active community with topic-specific channels (rendering, C++, networking, animation).
- **[Epic's official roadmap](https://portal.productboard.com/epicgames/1-unreal-engine-public-roadmap)** — what's coming, useful given how fast Nanite/Lumen evolve (Chapter 9).

> **Suggested path for a complete beginner:** read *Game Programming Patterns* (or at least its game-loop and component chapters) → do Epic's "Your First Hour in Unreal Engine" → build the Third Person template into a tiny game following a GameDev.tv or Tom Looman project → return to this guide chapter by chapter to understand *why* each system works the way it does.
