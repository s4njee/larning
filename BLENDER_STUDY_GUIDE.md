# Blender — A Conceptual Guide

A high-level, concept-first guide to Blender — the free, open-source 3D creation suite. This guide does not attempt to document every button; Blender is too vast for that. Instead it builds the mental framework: what each major system does, why it exists, how the pieces connect, and the vocabulary you need to learn the rest on your own. Rigging and animation get dedicated depth.

Primary references: [Blender Manual](https://docs.blender.org/manual/en/latest/), [Blender Reference](https://docs.blender.org/api/current/), [Blender Studio](https://studio.blender.org/)

> This guide targets Blender 4.x (LTS). The interface and concepts have been stable since the 2.8 redesign; version-specific notes are called out where relevant.

---

## Table of Contents

1. [The Mental Model](#1-the-mental-model)
2. [The Interface & Navigation](#2-the-interface--navigation)
3. [Objects, Scenes & Collections](#3-objects-scenes--collections)
4. [Modes — The Central Concept](#4-modes--the-central-concept)
5. [Modeling](#5-modeling)
6. [Modifiers & Non-Destructive Workflows](#6-modifiers--non-destructive-workflows)
7. [Materials & Shading](#7-materials--shading)
8. [UV Mapping & Texturing](#8-uv-mapping--texturing)
9. [Lighting](#9-lighting)
10. [Cameras & Rendering](#10-cameras--rendering)
11. [Sculpting](#11-sculpting)
12. [Rigging](#12-rigging)
13. [Animation](#13-animation)
14. [Geometry Nodes](#14-geometry-nodes)
15. [Particles & Physics](#15-particles--physics)
16. [Compositing & Post-Processing](#16-compositing--post-processing)
17. [Video Editing](#17-video-editing)
18. [Add-ons & Scripting](#18-add-ons--scripting)
19. [File Management & Production Workflows](#19-file-management--production-workflows)
20. [Where to Go Next](#20-where-to-go-next)
21. [Mastery Checklist](#21-mastery-checklist)

---

## 1. The Mental Model

### What Blender Is

Blender is a **complete 3D creation pipeline in a single application**. Modeling, sculpting, rigging, animation, simulation, rendering, compositing, motion tracking, and video editing — all under one roof. Most commercial studios spread these across Maya, ZBrush, Houdini, Nuke, After Effects, and Premiere. Blender does all of it, free and open-source, and since version 2.8 (2019) the interface is genuinely competitive.

The consequence: Blender is enormous. No one uses every feature. A character artist lives in sculpting and retopology. A motion-graphics designer lives in Geometry Nodes and the shader editor. An animator lives in the timeline and the graph editor. The guide is structured so you can read the concepts that matter to your path and skip the rest.

### The Pipeline Mindset

Every 3D project follows roughly the same pipeline, and Blender has a system for each stage:

```
Concept → Model → UV Unwrap → Texture/Material → Rig → Animate → Light → Render → Composite → Output
```

Not every project uses every stage. A product render skips rigging and animation. A motion-graphics piece might skip modeling entirely (Geometry Nodes can generate everything procedurally). But understanding the pipeline tells you *why* each system exists and *when* you reach for it.

### The Data Model

Blender's internal data model has a shape that explains most of its behavior:

- A **`.blend` file** is a self-contained database. It holds everything: meshes, materials, textures, animations, render settings, even the UI layout.
- Data is organized into **data-blocks**. A mesh is a data-block. A material is a data-block. An armature is a data-block. Every data-block has a name and a user count.
- **Objects** are containers that reference data-blocks. An object in the scene says "I am at position X, rotated by Y, and I display *this mesh* with *this material*." Multiple objects can share the same mesh data-block — this is **instancing**, and it's how you put a thousand identical trees in a scene without a thousand copies of the geometry.
- Data-blocks with **zero users** (nothing references them) are orphaned and cleaned up on save — unless you give them a **fake user** (the shield icon) to keep them around.

This user-count system is why things sometimes "disappear" when you think you saved them. If a material has zero users (it's not assigned to any object), Blender discards it on reload. The shield icon prevents that.

### Coordinate System

Blender uses a **right-handed coordinate system** with **Z-up**:

- **X** = left/right (red)
- **Y** = forward/back (green)  
- **Z** = up/down (blue)

This differs from some engines (Unity uses Y-up). It matters when exporting. The FBX exporter handles the conversion automatically, but knowing the convention prevents confusion.

---

## 2. The Interface & Navigation

### The Editor Paradigm

Blender's interface is built on a single idea: **the entire window is divided into editors, and any editor area can display any editor type.** The 3D viewport, the timeline, the properties panel, the outliner — these are all *editor types*. You can split any area, join areas, and change any area to any editor type. This makes the interface infinitely customizable but initially overwhelming.

The key editors:

| Editor | Purpose |
|---|---|
| **3D Viewport** | The main workspace — see and manipulate objects in 3D space |
| **Outliner** | Hierarchical view of everything in the scene (the "file tree") |
| **Properties** | Context-sensitive panels for the active object, scene, render, etc. |
| **Timeline** | Scrub through animation time; play/pause |
| **Graph Editor** | Edit animation curves (the "value over time" editor) |
| **Dope Sheet** | Overview of all keyframes across all objects |
| **Shader Editor** | Node-based material/shader editing |
| **Geometry Node Editor** | Node-based procedural geometry |
| **Compositor** | Node-based post-processing of rendered images |
| **UV Editor** | Unwrap and edit UV maps |
| **Image Editor** | View and paint textures |
| **Text Editor** | Write Python scripts |
| **Preferences** | Global settings, add-ons, keymaps |

### Workspaces

Workspaces are **saved editor layouts**. The default file ships with: Layout, Modeling, Sculpting, UV Editing, Texture Paint, Shading, Animation, Rendering, Compositing, and Geometry Nodes. Each is just a preset arrangement of editors — you can customize them or create your own.

Think of workspaces as task-specific desks. You don't model in the Animation workspace or animate in the Sculpting workspace. The tabs along the top switch contexts.

### 3D Viewport Navigation

The viewport is where you spend most of your time. Navigation:

- **Middle mouse button (MMB)** — orbit
- **Shift + MMB** — pan
- **Scroll wheel** — zoom
- **Numpad 1/3/7** — front/right/top orthographic views
- **Numpad 5** — toggle perspective/orthographic
- **Numpad 0** — camera view
- **Numpad .** — focus on selected object

If you have no numpad (laptop), enable "Emulate Numpad" in Preferences → Input.

### The Operator System

Almost everything you do in Blender is an **operator** — a named, repeatable action. When you press `G` to grab (move) an object, you're invoking the `bpy.ops.transform.translate` operator. This matters because:

1. **Every operator appears in the F3 search menu.** If you forget a hotkey, press F3 and type what you want.
2. **The last operator's settings appear in the bottom-left panel** after you execute it. You can tweak parameters after the fact.
3. **Operators are scriptable** — the Python API mirrors the operator system exactly.

### Essential Hotkeys

Blender is hotkey-driven. You *can* use menus for everything, but it's painfully slow. The essential set:

| Key | Action |
|---|---|
| `G` | Grab (move) |
| `R` | Rotate |
| `S` | Scale |
| `G/R/S` then `X/Y/Z` | Constrain to axis |
| `G` then type `3` | Move exactly 3 units |
| `Tab` | Toggle Object/Edit mode |
| `A` | Select all |
| `Alt+A` | Deselect all |
| `X` or `Delete` | Delete |
| `Shift+A` | Add menu (new objects) |
| `Ctrl+Z` / `Ctrl+Shift+Z` | Undo / redo |
| `F3` | Search all operators |
| `N` | Toggle side panel (transform, item info) |
| `T` | Toggle toolbar |
| `H` / `Alt+H` | Hide / unhide selected |
| `Ctrl+P` | Parent objects |
| `Shift+D` | Duplicate |
| `Alt+D` | Linked duplicate (shared data-block) |

---

## 3. Objects, Scenes & Collections

### Object Types

An object is a thing in 3D space with a position, rotation, and scale (its **transform**). Object types include:

| Type | What it is |
|---|---|
| **Mesh** | Vertices, edges, and faces — the most common geometry type |
| **Curve** | Bézier or NURBS curves; can be rendered or used as paths |
| **Surface** | NURBS surfaces (rarely used directly) |
| **Text** | 3D text objects (converted to mesh for detailed work) |
| **Empty** | An invisible transform — used as a parent, target, or reference point |
| **Armature** | A skeleton for rigging (bones) |
| **Camera** | The viewpoint for rendering |
| **Light** | Illumination source (point, sun, spot, area) |
| **Lattice** | A deformation cage for bending/warping other objects |
| **Force Field** | Invisible physics forces (wind, vortex, turbulence) |

### Collections

Collections are Blender's organizational system — think of them as folders. Objects live in collections. Collections can be nested. Each collection can be toggled visible/hidden, selectable/unselectable, or excluded from the view layer entirely.

Common pattern: organize by type (`Lights`, `Characters`, `Environment`) or by purpose (`Hero_Assets`, `Background`, `Ref_Images`). In large scenes, good collection hygiene is the difference between a manageable project and chaos.

### Scenes & View Layers

A `.blend` file can contain multiple **scenes**. Each scene has its own set of objects, world settings, and render settings. Use cases: a multi-shot animation, or separate scenes for modeling reference and final render.

A **view layer** is a filtered view of a scene — you can include/exclude specific collections per view layer. Primarily used for compositing: render the character on one layer, the background on another, combine in the compositor.

### The Parent-Child Hierarchy

Objects can be parented to other objects (`Ctrl+P`). The child inherits the parent's transform — move the parent, the child follows. The child can still have its own local transform on top.

Common uses:
- Parent a sword to a character's hand bone
- Parent all parts of a vehicle to an empty at its center
- Parent lights to a rig so they move with the camera

The Outliner shows the hierarchy as nested items.

---

## 4. Modes — The Central Concept

### Why Modes Exist

Blender's mode system is the single most important concept to internalize. **Modes change what you can do to the selected object.** In Object Mode, you move, rotate, and scale the whole object. In Edit Mode, you manipulate the individual vertices, edges, and faces that make up the object's geometry.

Modes exist because the same selection, the same hotkeys, and the same viewport need to mean different things depending on what level you're working at. `G` in Object Mode moves the entire object. `G` in Edit Mode moves the selected vertex.

### The Modes

| Mode | Available on | What you do |
|---|---|---|
| **Object Mode** | Everything | Select, transform, parent, duplicate whole objects |
| **Edit Mode** | Meshes, curves, surfaces, text, armatures, lattices | Modify the internal geometry — vertices, edges, faces, control points, bones |
| **Sculpt Mode** | Meshes | Freeform sculpting with brushes — push, pull, smooth, carve |
| **Vertex Paint** | Meshes | Paint color data onto vertices |
| **Weight Paint** | Meshes | Paint bone influence weights (for rigging) |
| **Texture Paint** | Meshes | Paint directly onto the surface/UV texture |
| **Pose Mode** | Armatures | Pose and keyframe bones for animation |

The mode is **per-object**. You enter Edit Mode *on* a specific mesh. Tab toggles between Object Mode and the last-used edit mode for the selected object.

### The Trap

New users frequently get confused because they're in the wrong mode. You're trying to select a vertex but nothing happens — you're in Object Mode. You're trying to move the whole object but only one vertex moves — you're in Edit Mode. **Always check your mode** (displayed in the top-left of the viewport header).

---

## 5. Modeling

### The Mesh Primitive

3D modeling in Blender ([manual: Modeling](https://docs.blender.org/manual/en/latest/modeling/index.html)) starts with mesh primitives — simple shapes you add to the scene and then reshape:

- **Plane** — a single flat quad (4 vertices)
- **Cube** — the most common starting point
- **Sphere** (UV sphere or Ico sphere) — the UV sphere has latitude/longitude topology; the Ico sphere has more even triangle distribution
- **Cylinder, Cone, Torus** — other common starting shapes

All modeling is some variation of: start with a primitive, enter Edit Mode, and reshape it.

### Vertices, Edges, Faces

A mesh is made of three geometric elements:

- **Vertex** — a point in 3D space
- **Edge** — a line connecting two vertices
- **Face** — a flat surface enclosed by edges (typically 3 or 4 edges — tris or quads)

In Edit Mode, you can select and manipulate any of these. The `1/2/3` keys at the top of the keyboard (not numpad) switch between vertex, edge, and face select modes.

### Topology

**Topology** is the structure of your mesh — how vertices, edges, and faces are connected. It's not about the shape; it's about the *flow* of the geometry.

Why topology matters:
- **Subdivision** — if your mesh is all quads (four-sided faces) with good edge flow, it subdivides smoothly. Triangles and n-gons (5+ sided faces) create pinching artifacts.
- **Deformation** — a character mesh needs edge loops that follow the muscles and joints. Bad topology → ugly deformation when the character moves.
- **Performance** — game engines care about polygon count. Fewer polygons with good topology looks better than more polygons with bad topology.

The universal rule: **use quads wherever possible, especially on anything that will be subdivided or deformed.** Triangles are acceptable on flat, non-deforming surfaces. N-gons are acceptable only on perfectly flat surfaces that won't be subdivided.

### Key Modeling Operations

| Operation | Hotkey | What it does |
|---|---|---|
| **Extrude** | `E` | Duplicates selected geometry and moves it outward — the primary way to "grow" a mesh |
| **Inset** | `I` | Creates a smaller face inside the selected face — for adding detail |
| **Bevel** | `Ctrl+B` | Rounds or chamfers edges — essential for realistic hard-surface models |
| **Loop Cut** | `Ctrl+R` | Adds a ring of edges around the mesh — for adding topology |
| **Merge** | `M` | Combines vertices into one — for closing gaps |
| **Fill** | `F` | Creates a face from selected edges or vertices |
| **Knife** | `K` | Free-hand cutting tool — adds edges wherever you draw |
| **Bridge Edge Loops** | Menu | Connects two edge loops with faces — for joining parts |
| **Subdivide** | Right-click menu | Splits each face into smaller faces |

### Box Modeling vs. Poly-by-Poly

Two fundamental approaches:

- **Box modeling**: Start with a cube (or other primitive), add loop cuts, extrude, and reshape until you have the final form. Good for hard-surface objects (machines, architecture, props).
- **Poly-by-poly**: Build the mesh one face at a time by extruding edges. Good for organic shapes where you need precise topology from the start (faces, hands).

Most workflows combine both: block out the shape with box modeling, then refine topology as needed.

### Normals

Every face has a **normal** — a vector pointing perpendicular to the surface, indicating which direction is "outside." Normals determine:

- Which side of a face is visible (back-face culling)
- How light bounces off the surface (shading)
- Which direction modifiers push geometry

If a face looks dark or inside-out, its normal is probably flipped. Fix with: Mesh menu → Normals → Recalculate Outside (`Shift+N`).

**Smooth vs. Flat shading**: Flat shading shows each face as a distinct facet. Smooth shading interpolates normals across faces so the surface looks curved. In practice, you use smooth shading everywhere and control the hard edges with **Auto Smooth** (angle-based) or **sharp edges** (manually marked).

---

## 6. Modifiers & Non-Destructive Workflows

### What Modifiers Are

[Modifiers](https://docs.blender.org/manual/en/latest/modeling/modifiers/index.html) are **non-destructive operations** applied to an object's data. They sit in a stack (Properties → Modifier tab, the wrench icon) and are evaluated top-to-bottom. The key word is non-destructive — the original mesh is unchanged. You can adjust parameters, reorder, disable, or remove modifiers at any time.

This is one of Blender's most powerful concepts. Instead of permanently subdividing a mesh, you add a Subdivision Surface modifier and can change the level at any time. Instead of permanently cutting a mesh in half and mirroring it, you add a Mirror modifier and model only one side.

### The Modifier Stack

Modifiers are evaluated sequentially. Order matters:

```
Original Mesh
    ↓
Mirror (mirror across X axis)
    ↓
Subdivision Surface (smooth the geometry)
    ↓
Solidify (give the surface thickness)
    ↓
Final Displayed Result
```

Swapping the order of Subdivision and Solidify produces a completely different result. Drag modifiers in the stack to reorder.

### Essential Modifiers

**Generate modifiers** create or modify geometry:

| Modifier | Purpose |
|---|---|
| **Subdivision Surface** | Smooths mesh by subdividing — *the* most-used modifier. Controls "Levels Viewport" (preview quality) and "Render" (final quality) separately |
| **Mirror** | Mirrors geometry across one or more axes — model half, get the whole thing. Essential for symmetrical objects |
| **Array** | Duplicates the object in a line, grid, or along a curve — for fences, chains, stairs |
| **Boolean** | Combines two meshes: union, intersection, or difference (cut one from another) — for hard-surface modeling |
| **Solidify** | Gives a surface thickness — turns a flat plane into a wall |
| **Bevel** | Adds bevels to edges procedurally — for non-destructive edge rounding |
| **Screw** | Revolves a profile curve around an axis — for goblets, vases, bolts |
| **Remesh** | Regenerates the mesh topology — useful after Boolean operations or sculpting |
| **Skin** | Generates a mesh around a skeleton of vertices/edges — for quick organic shapes |
| **Decimate** | Reduces polygon count — for game-ready optimization |
| **Wireframe** | Converts edges to tubes — for wireframe renders or cage structures |

**Deform modifiers** change the shape without changing topology:

| Modifier | Purpose |
|---|---|
| **Armature** | Deforms the mesh based on bone positions — *the* rigging modifier |
| **Lattice** | Deforms using a lattice cage — good for broad-stroke reshaping |
| **Curve** | Deforms along a curve — for roads, pipes, tentacles |
| **Shrinkwrap** | Projects/snaps one mesh onto another's surface |
| **Simple Deform** | Twist, bend, taper, or stretch |
| **Cast** | Reshapes toward a sphere, cylinder, or cuboid |
| **Wave** | Animatable wave deformation |
| **Displace** | Deforms based on a texture — for terrain, surface detail |

### Apply vs. Keep

When you **apply** a modifier (`Ctrl+A` on the modifier), the operation becomes permanent — the mesh is modified and the modifier is removed. Apply when:

- You need to edit the result directly
- You're exporting to a format that doesn't support modifiers (game engine)
- You're done iterating on that parameter

Keep modifiers unapplied as long as possible to maintain flexibility.

---

## 7. Materials & Shading

### What a Material Is

A material defines how a surface looks — its color, roughness, transparency, emission, and how it reacts to light. In Blender, materials are built using a **node-based shader system** in the Shader Editor.

Every material is a tree of nodes that feeds into a **shader output**. The most common starting point is the **[Principled BSDF](https://docs.blender.org/manual/en/latest/render/shader_nodes/shader/principled.html)** node — a physically-based shader that handles most real-world surfaces with a single node.

### PBR — Physically Based Rendering

Blender's shader system follows **PBR (Physically Based Rendering)** principles: materials are defined by measurable physical properties rather than artistic hacks. The Principled BSDF exposes:

| Property | Controls | Range |
|---|---|---|
| **Base Color** | The surface color (albedo) | Color or texture |
| **Metallic** | Is it metal or non-metal? | 0 (dielectric) to 1 (metal). Almost always exactly 0 or exactly 1 — real materials are one or the other |
| **Roughness** | How blurry are reflections? | 0 (mirror) to 1 (matte). Most real materials are 0.3–0.8 |
| **Specular IOR Level** | Strength of reflections at glancing angles | Default 0.5 works for most surfaces |
| **Transmission** | Transparency (glass, water) | 0 (opaque) to 1 (fully transmissive) |
| **IOR** | Index of refraction | 1.0 (air) to ~2.4 (diamond). Glass = 1.45, water = 1.33 |
| **Emission Color / Strength** | Self-illumination | For glowing surfaces, screens, fire |
| **Alpha** | Opacity | 0 (invisible) to 1 (fully visible). Needs blend mode set in material settings |
| **Normal** | Surface detail via normal maps | Connect a Normal Map node |
| **Coat** | Clear-coat layer (car paint, lacquer) | Weight 0–1 |
| **Sheen** | Soft "fuzz" layer (velvet, fabric) | Weight 0–1 |
| **Subsurface** | Light scattering inside the surface (skin, wax, marble) | Weight 0–1 with a scatter radius |

### Texture Maps

Real-world materials are rarely a single color. Textures (images) are plugged into shader inputs to add detail:

| Map Type | Plugs into | Purpose |
|---|---|---|
| **Diffuse / Albedo** | Base Color | Surface color variation |
| **Roughness** | Roughness | Per-pixel roughness variation |
| **Metallic** | Metallic | Defines which areas are metal |
| **Normal** | Normal (via Normal Map node) | Fakes surface bumps without extra geometry |
| **Displacement** | Material Output → Displacement | Actually moves geometry (requires subdivision) |
| **Ambient Occlusion** | Multiply with Base Color | Contact shadows (less needed with real-time AO) |
| **Emission** | Emission Color | Glowing areas |
| **Opacity / Alpha** | Alpha | Transparent areas (leaves, fences) |

Texture workflow: connect an **Image Texture** node to the input, with a **Texture Coordinate** and **Mapping** node controlling placement. The UV coordinate is the most common method — it uses the mesh's UV map (see next section).

### Procedural Textures

Blender includes built-in procedural textures — math-generated patterns that don't require image files:

- **Noise** — organic randomness (clouds, terrain)
- **Voronoi** — cell patterns (scales, cracked earth, stone tiles)
- **Wave** — stripes or rings (wood grain, water ripples)
- **Musgrave** — fractal noise (detailed terrain)
- **Gradient** — linear, spherical, quadratic falloff
- **Checker** — checkerboard pattern
- **Brick** — configurable brick pattern

Procedural textures are resolution-independent (they never pixelate) and infinitely tileable. They can be mixed, layered, and distorted through node chains to create complex materials without any image files.

---

## 8. UV Mapping & Texturing

### The Problem UV Mapping Solves

A 3D surface is, well, 3D. A texture is a flat 2D image. **UV mapping** is the process of defining how the 2D image wraps onto the 3D surface — it's the relationship between every point on the mesh and a point on the texture.

The name comes from the coordinate system: the texture uses **U** and **V** axes (because X, Y, Z are already taken by 3D space).

### The Concept

Imagine cutting open a cardboard box and laying it flat. The flattened box is the UV layout. Each face of the 3D mesh maps to a region of the flat texture. The UV Editor shows this flattened view.

If you skip UV mapping and just apply a texture, Blender uses a default projection (often generated coordinates) which stretches horribly on complex shapes. Proper UV mapping eliminates stretching.

### Unwrapping Methods

Blender provides several unwrapping algorithms (Edit Mode → UV menu):

| Method | Use Case |
|---|---|
| **Unwrap** (default) | General-purpose conformal unwrap. Requires seams to be marked |
| **Smart UV Project** | Automatic — splits the mesh into flat-ish chunks. Good for hard-surface objects where you don't need precise control |
| **Cube/Cylinder/Sphere Projection** | Projects from a simple shape — works when the mesh roughly matches that shape |
| **Project from View** | Projects from the current viewport angle — for decals or view-dependent textures |

### Seams

For the default Unwrap method, you mark **seams** — edges where the mesh is "cut" for flattening. Think of seams on a stuffed animal: they're where the fabric panels meet. Place seams:

- Along edges that won't be visible (back of a head, underside of an object)
- Where the surface changes direction sharply
- Around separate features (eyes, fingers)

Mark seams in Edit Mode: select edges → Edge menu → Mark Seam.

### Texture Painting

Blender can paint directly onto the 3D surface (Texture Paint mode) or onto the UV layout (Image Editor). This is useful for hand-painted textures, stylized art, or touch-ups. For photorealistic work, most artists create textures in external tools (Substance Painter, Quixel Mixer) and import them.

---

## 9. Lighting

### Light Types

Blender has four light object types:

| Light | Behavior | Use |
|---|---|---|
| **Point** | Emits in all directions from a single point | Light bulbs, candles, small practicals |
| **Sun** | Parallel rays from infinitely far away, uniform across the scene | Daylight, moonlight. Position doesn't matter — only rotation |
| **Spot** | Cone of light from a point | Stage lights, flashlights, car headlights |
| **Area** | Emits from a flat rectangle or disc | Soft studio lighting, windows, monitors. Larger area = softer shadows |

### Three-Point Lighting

The foundational lighting setup in photography, film, and 3D:

1. **Key light** — the main light source. Determines the dominant shadow direction. Placed to one side and above the subject.
2. **Fill light** — softer, dimmer light on the opposite side. Fills in shadows so they're not pitch-black. Often an area light or bounced light.
3. **Rim/Back light** — behind the subject, creating an edge highlight that separates the subject from the background.

This setup works for almost every situation. Master it before getting fancy.

### HDRI Environment Lighting

An **HDRI (High Dynamic Range Image)** is a 360° photograph that provides both lighting and a background for the scene. It's the fastest way to get realistic, natural lighting — plug the HDRI into the World shader's Environment Texture node.

Free HDRI sources: [Poly Haven](https://polyhaven.com/), [ambientCG](https://ambientcg.com/).

### Light Behavior in Render Engines

- **EEVEE** (real-time): Lights need manual shadow setup. Area lights don't automatically create soft shadows without enabling "Contact Shadows." Light probes help with indirect lighting.
- **Cycles** (path tracer): All lighting is physically accurate. Area lights naturally create soft shadows. Indirect light bounces are computed automatically. More realistic, but slower.

---

## 10. Cameras & Rendering

### Camera Concepts

The camera defines what gets rendered. Key properties:

- **Focal Length** — measured in mm. Wide-angle (18–35mm) exaggerates depth, creates dramatic perspectives. Normal (50mm) approximates human vision. Telephoto (85–200mm) compresses depth, flattens the scene.
- **Sensor Size** — affects field of view for a given focal length. Default is 36mm (full-frame equivalent).
- **Depth of Field** — blurs objects that aren't at the focus distance. Controlled by **F-Stop** (lower = more blur) and **Focus Distance** (or focus on a specific object).
- **Clipping** — near/far clip planes determine the visible range. Objects outside this range are invisible.

### Render Engines

Blender ships with three render engines:

| Engine | Type | Speed | Quality | Use Case |
|---|---|---|---|---|
| **[EEVEE](https://docs.blender.org/manual/en/latest/render/eevee/index.html)** | Rasterization (real-time) | Fast (seconds) | Good, approximate | Previews, stylized work, animation, games-adjacent |
| **[Cycles](https://docs.blender.org/manual/en/latest/render/cycles/index.html)** | Path tracing (physically accurate) | Slow (minutes–hours) | Photorealistic | Final renders, product viz, film, arch-viz |
| **Workbench** | OpenGL viewport render | Instant | Basic (flat, matcap) | Clay renders, quick previews, modeling checks |

**EEVEE Next** (Blender 4.2+) is a major upgrade: ray-traced shadows, reflections, and global illumination bring it much closer to Cycles quality while maintaining real-time performance.

### Render Settings That Matter

- **Resolution** — output size in pixels. 1920×1080 for HD, 3840×2160 for 4K.
- **Samples** — (Cycles) how many light rays per pixel. More samples = less noise = slower. 128–512 is typical for final renders with denoising.
- **Denoiser** — AI-based noise reduction that lets you use fewer samples. OptiX (NVIDIA) or OpenImageDenoise (CPU/Intel). Dramatically reduces render time.
- **Color Management** — use **Filmic** or **AgX** (Blender 4.0+) tone mapping for photorealistic results. The default "Standard" looks washed out.
- **Output Format** — PNG for stills, OpenEXR for compositing (32-bit color), FFmpeg for video.

### Rendering Animation

For animation, you render a **sequence of images** (one per frame), not a video file directly. Why: if the render crashes at frame 347 of 500, you've lost nothing — just restart from 347. You assemble the image sequence into video afterward (in the Video Sequencer or an external tool).

Output format for animation frames: PNG (quick, lossy-free, 8-bit) or OpenEXR (for compositing flexibility).

---

## 11. Sculpting

### The Concept

Sculpting treats the mesh like digital clay. Instead of manipulating individual vertices, you push, pull, smooth, and carve with **brushes** — the same metaphor as digital painting, but in 3D. It's the most intuitive way to create organic shapes (characters, creatures, terrain, organic props).

Sculpting requires **high polygon counts** — thousands to millions of faces. A smooth sphere of 500 polygons can't hold the detail of a human face. A sphere of 2 million polygons can.

### Key Brushes

| Brush | What it does |
|---|---|
| **Draw** | Raises the surface where you paint — the default "add clay" brush |
| **Clay Strips** | Adds flat strips of "clay" — great for building up broad forms |
| **Smooth** | Smooths bumps and irregularities. Hold `Shift` to temporarily smooth with any brush |
| **Grab** | Pulls the surface as if grabbing and dragging — for large-scale shape changes |
| **Crease** | Creates sharp creases and folds — for wrinkles, folds, panel lines |
| **Inflate** | Expands the surface outward — for puffing up areas |
| **Flatten** | Flattens high points to a plane — for creating flat surfaces |
| **Scrape** | Scrapes away high points — like a chisel |
| **Mask** | Paints a mask that protects areas from sculpting |
| **Trim** | Cuts away geometry to a plane — for hard-surface detailing |

### Dynamic Topology (Dyntopo)

By default, sculpting moves existing vertices. If the mesh doesn't have enough geometry where you're sculpting, you get blobby results. **Dynamic Topology** solves this by automatically adding geometry where you sculpt and keeping low detail where you don't.

Dyntopo is great for concept sculpting when you don't care about topology. For production work (animation, texturing), you sculpt with Dyntopo first, then **retopologize** — rebuild the mesh with clean quad-based topology that deforms properly.

### Multires Modifier

The **Multiresolution modifier** is an alternative to Dyntopo. It works like Subdivision Surface but lets you sculpt at each subdivision level. The advantage: the base mesh retains clean topology, and the sculpted detail lives on top as displacement.

Workflow: start with a clean base mesh → add Multires → subdivide to the level you need → sculpt the high-res detail → bake the detail as a normal/displacement map onto the low-res version.

---

## 12. Rigging

Rigging is the process of building a control system that lets you pose and animate a 3D model. It bridges modeling and animation: the modeler creates the static mesh, the rigger makes it movable, and the animator brings it to life.

### The Armature

An **[armature](https://docs.blender.org/manual/en/latest/animation/armatures/index.html)** is Blender's skeleton system — a hierarchy of **bones**. You add an armature (Shift+A → Armature), which starts as a single bone. In Edit Mode on the armature, you build out the skeleton by extruding (`E`) new bones from existing ones.

Each bone has:
- A **head** (base/root of the bone, the ball joint)
- A **tail** (tip of the bone)
- A **roll** angle (rotation around its own axis — critical for predictable rotation)

Bones form a **parent-child hierarchy**. Moving a parent bone moves all its children. An upper arm bone is parent to a forearm bone, which is parent to a hand bone.

### Bone Orientation, Roll & Symmetry

Three bone properties cause most beginner rigging pain, and all three are about *orientation* rather than position:

- **Roll** — the rotation of a bone around its own length. Two bones can have identical head and tail positions but different rolls, and they'll rotate around different axes. If a character's fingers curl sideways instead of into a fist, the bone rolls are wrong. Select the bones and use **Armature → Bone Roll → Recalculate Roll** (`Ctrl+N` in armature Edit Mode) to align them consistently (e.g., "Global +Z Axis" or "View").
- **Connected vs. disconnected** — a **connected** bone's head is glued to its parent's tail, so moving the parent's tail drags the child. A **disconnected** bone is still parented (it inherits motion) but its head floats free anywhere. Arms and spines are usually connected; a pelvis bone or a free-floating control bone is disconnected. Toggle with **Alt+P** / **Ctrl+P** or the "Connected" checkbox.
- **Display mode** — bones draw as **Octahedral** (default cone — shows roll and direction), **Stick** (thin lines — less clutter on dense rigs), **B-Bone**, **Envelope**, or **Wireframe**. Octahedral while building, Stick or custom shapes while animating.

Turn on the bone's local axes (**Armature → Viewport Display → Axes**) while rigging so you can *see* which way each bone rotates. Predictable axes are the difference between a rig an animator enjoys and one they fight.

**Symmetry** halves the work on any bilateral creature. Name bones with a **`.L` / `.R` suffix** (`UpperArm.L`, `Hand.R`) and Blender treats them as mirror pairs everywhere:

- **X-Axis Mirror** (Armature → Tools, or the header toggle) — extrude or transform a `.L` bone and its `.R` twin mirrors automatically.
- **Symmetrize** (Armature menu) — build one whole side, then generate the opposite side, with names and rolls flipped, in one click.
- **Flip Names** repairs bones whose suffixes got out of sync.

The `.L`/`.R` convention isn't cosmetic — weight mirroring, pose flipping ("paste flipped pose"), and Rigify all depend on it.

### The Rigging Workflow

```
1. Model the mesh (neutral pose, T-pose or A-pose)
       ↓
2. Create the armature and position bones inside the mesh
       ↓
3. Parent the mesh to the armature ("Armature Deform")
       ↓
4. Paint vertex weights (which bones control which parts of the mesh)
       ↓
5. Add constraints (IK, limits, copy transforms) for animator-friendly controls
       ↓
6. Test by posing in Pose Mode
```

### Deform Bones vs. Control Bones

The single most important idea in production rigging: **the bones that deform the mesh are not the bones the animator touches.** A good rig has two layers.

- **Deform bones** are the actual skeleton — the bones bound to mesh vertices through weights. The animator never selects these directly. In Blender, only bones with the **"Deform"** checkbox enabled drive the Armature modifier; bones with it *off* can move things via constraints but skin nothing.
- **Control bones** (controllers, "the rig") are the handles the animator grabs: an IK hand control, a foot control, a master/root control, FK rotation controls. They carry custom shapes, live on their own bone collections, and drive the deform bones through **constraints** (Copy Transforms, IK, etc.).

```
Animator grabs →  CONTROL bones   (custom shapes, no deform)
                       │  constraints (IK, Copy Rotation…)
                       ▼
                  DEFORM bones    (skinned to the mesh via weights)
                       │  Armature modifier + vertex groups
                       ▼
                     The MESH
```

Why bother? Because this is what lets you offer an **IK hand and an FK elbow on the same arm**, a foot that rolls on one bone, sliders for facial poses, and limits that forbid impossible poses — none of which the raw deform skeleton can express. The simple "extrude bones, parent mesh, pose the bones directly" rig from the workflow above is the *deform layer only*. Everything that makes a rig pleasant to animate lives in the control layer on top. **Rigify** (below) generates both layers for you, which is why it's the usual recommendation.

### Bone Parenting — How the Mesh Follows the Skeleton

When you parent a mesh to an armature (`Ctrl+P` → Armature Deform), Blender creates an **Armature modifier** on the mesh. This modifier deforms the mesh based on bone positions. The connection between bones and mesh vertices is defined by **vertex groups**.

Each bone corresponds to a vertex group with the same name. The **weight** of each vertex in that group (0.0 to 1.0) determines how much that bone influences it. A vertex with weight 1.0 in the "UpperArm.L" group moves entirely with the left upper arm bone. A vertex with weight 0.5 in both "UpperArm.L" and "Forearm.L" blends between both — this is how elbows, shoulders, and other joints deform smoothly.

### The Armature Modifier — Skinning Options

Parenting with Armature Deform adds an **Armature modifier** to the mesh, and a few of its options matter:

- **Preserve Volume** switches to **dual-quaternion skinning** instead of the default linear blend. It dramatically reduces the "candy-wrapper" collapse where a twisting forearm or shoulder pinches to nothing. Turn it on for organic characters — it's the cheapest fix for twist deformation.
- **Vertex Groups vs. Bone Envelopes** — by default, deformation is driven by **vertex groups** (per-vertex weights — precise, and what you'll use 99% of the time). **Envelopes** give each bone a capsule of influence — fast to set up, imprecise, mostly for blocking or simple props.
- **Stack order matters** — the Armature is just another modifier. A Subdivision Surface *below* it subdivides the deformed result (smooth); *above* it deforms a smooth cage. For characters: deform first, subdivide after.

### Automatic Weights

When parenting the mesh to the armature, Blender offers **"With Automatic Weights"** — it tries to figure out which vertices belong to which bones based on proximity and bone heat diffusion. This works surprisingly well for simple rigs and gives you a starting point. But it's never perfect for production work — you'll always need to refine with weight painting.

### Weight Painting

**Weight Paint mode** is where you refine bone influence. The mesh is displayed as a heat map:

- **Blue** = 0.0 weight (no influence)
- **Green** = 0.5 (partial influence)
- **Red** = 1.0 (full influence)

You select a bone (in the armature), enter Weight Paint mode on the mesh, and paint weights. The key insight: **deformation problems are almost always weight painting problems.** If an elbow looks wrong when it bends, the weights around the elbow joint need fixing.

Weight painting tips:
- **Use the Smooth brush** to blend harsh transitions between bone influences
- **Enable "Show Zero Weights"** (in the overlay menu) — areas with zero weight turn black, making gaps obvious
- **Normalize weights** — every vertex's total weight across all groups should sum to 1.0. Blender can auto-normalize (enable in the tool options)
- **Lock vertex groups** you're not painting — prevents accidentally modifying them
- **Test as you paint** — pose the bone, see how it looks, adjust weights, repeat

### Mirroring Weights

You only need to weight-paint one side of a symmetric character. To copy weights across:

- The mesh's vertex groups are named after the bones, so they already carry `.L`/`.R` suffixes.
- In Weight Paint mode, enable the header's **X Mirror** option — painting a `.L` vertex also paints its `.R` mirror in real time (requires symmetric topology).
- Or paint one side fully, then **Weights → Mirror** (or **Symmetrize**) to flip the finished weights to the other side.

This halves the work and guarantees the sides actually match — hand-painting both sides independently never produces true symmetry.

### Forward Kinematics (FK) vs. Inverse Kinematics (IK)

**FK (Forward Kinematics)**: You rotate each bone in the chain individually. Rotate the upper arm, then the forearm, then the hand. This gives you precise control over every joint but is tedious for common motions.

**IK (Inverse Kinematics)**: You place a **target** (an empty or a bone), and the bone chain automatically solves how to reach it. Move the IK target and the whole arm follows. The shoulder, elbow, and wrist all rotate to reach the target position.

```
FK:  Rotate shoulder → then rotate elbow → then rotate wrist
     (build the pose from root to tip)

IK:  Place the hand target → the arm figures itself out
     (define where the end should be, solve backwards)
```

To set up IK: add an **Inverse Kinematics constraint** to the last bone in the chain, pointing at a target bone or empty. Set the **chain length** (how many bones the IK affects — 0 means the whole chain up to the root).

### IK/FK Switching & Auto-IK

Real rigs offer *both* FK and IK on the same limb, because each wins in different shots. FK arcs feel natural for a swinging arm; IK keeps a hand planted on a table or a foot locked to the floor. Animators switch between them per shot — sometimes mid-shot.

- A control rig exposes a **custom property** (often an "IK/FK" slider, 0–1) that blends a constraint's **influence** between the two solvers. Rigify builds this in, plus a **snap** operator so the limb doesn't jump when you switch.
- **Chain length** on the IK constraint decides how far up the solve propagates (2 for forearm + upper arm, more for a spine). Length 0 means "all the way to the root," which you rarely want.
- **Auto IK** (a Pose-Mode header toggle in the Tool panel) drags a bone chain IK-style with no setup — handy for quickly posing a plain FK skeleton, but not a substitute for a real IK control.

The mental model: **IK defines where the *end* of the chain goes and solves the joints backward; FK builds the pose from the root outward.** Choose per shot based on what must stay still — a planted hand or foot wants IK, a free-swinging limb wants FK.

### Pole Targets

IK solves where the chain ends up, but not the *orientation* of the in-between joints. An elbow can point in any direction while the hand stays in place. A **pole target** (another empty or bone) controls which direction the elbow (or knee) points. Place it in front of the knee/behind the elbow.

### Spline IK

Where regular IK reaches a point, **Spline IK** makes a bone chain follow a **curve**. The chain bends smoothly along the spline, and you animate by editing the curve (or by hooking its control points to bones). This is the tool for anything long and flexible: **tails, tentacles, ropes, snakes, spines, antennae**. Add the chain, give the last bone a **Spline IK constraint**, point it at a curve, and set the chain length.

### Bendy Bones (B-Bones)

A normal bone is rigid — a straight segment. A **Bendy Bone (B-Bone)** is a single bone that **curves**, subdividing itself into segments that interpolate a smooth bend between its endpoints. One B-Bone does the work of a multi-bone chain for organic curvature.

- Set a bone's **Segments** (Bone properties → Bendy Bones) above 1 to enable curving.
- Curvature is driven by **handles** — usually the previous/next bones (like a Bézier curve's tangents), or dedicated **Custom Handle** bones.
- Per-end **Ease In/Out, Curvature, Roll, and Scale** give you cartoony squash, smooth spine bends, lips, fingers, and rubber-hose limbs with far fewer bones.

B-Bones are a Blender signature feature — Rigify leans on them for spines and faces. The trade-off: they cost more to compute and are overkill for rigid/mechanical rigs.

### Bone Constraints

Constraints modify bone behavior. They're the building blocks of a good control rig:

| Constraint | Purpose |
|---|---|
| **Inverse Kinematics** | IK chain solving (arms, legs) |
| **Copy Location / Rotation / Scale** | Make one bone follow another (partially or fully) |
| **Limit Location / Rotation / Scale** | Prevent a bone from moving/rotating beyond a range (e.g., an elbow can't bend backward) |
| **Damped Track / Track To** | Point a bone at a target (eye tracking, head look-at) |
| **Stretch To** | Bone stretches to reach a target (rubber-hose animation, squash-and-stretch) |
| **Transformation** | Map one bone's transform to another's (a slider bone controls a blend shape) |
| **Action** | Drive a baked animation clip from another bone's value |
| **Child Of** | Dynamic parenting (pick up an object, hand it off) — switchable at animation time |
| **Floor** | Prevents a bone from going below a surface (feet on ground) |

Two settings appear on almost every constraint:

- **Influence** (0–1) blends the constraint on and off — and is itself keyable, so you can switch IK off at frame 1 and on at frame 20, or fade a "look at" in and out.
- **Target/Owner space** (World, Local, Pose, Local With Parent) sets *which coordinate frame* the constraint reads and writes in. Mismatched spaces are the usual reason a constraint "does something weird"; for most copy/limit constraints, Local-to-Local behaves intuitively.

Constraints also **stack and evaluate top to bottom**, so a Limit Rotation placed *after* a Copy Rotation clamps the copied result. Order is part of the rig's logic.

### Custom Bone Shapes & Bone Collections

Two features turn a tangle of bones into a usable interface:

- **Custom bone shapes (widgets)** — any bone can *display* as a chosen mesh object instead of the default octahedron (Bone properties → Viewport Display → **Custom Object**). Animators then grab a clear circle around the wrist, an arrow on the foot, or a cog on a mechanical control — shapes that read at a glance and signal what each control does. The widget is display-only; it doesn't deform or render.
- **Bone collections** (called *bone layers* before 4.0) — group bones and toggle their visibility together. A clean rig parks the deform bones and mechanism on hidden collections, leaving only controls visible. The animator shows "Face" controls for a close-up, "Body" controls for a walk, and never sees the wiring.

Add **bone colors** (per bone or per collection) — left side one hue, right side another, IK vs. FK a third — and the rig becomes self-documenting. This presentation layer is what separates a rig an animator *wants* to use from a pile of bones they have to decode.

### Rigify — Blender's Auto-Rig Add-on

Building a full character rig from scratch is a weeks-long task for a professional. **[Rigify](https://docs.blender.org/manual/en/latest/addons/rigging/rigify/index.html)** (bundled add-on, enable in Preferences) generates a complete, animator-friendly rig from a template:

1. Add a Rigify **meta-rig** (Shift+A → Armature → choose a template — human, cat, horse, etc.)
2. Scale and position the meta-rig bones to fit your mesh (Edit Mode)
3. Click **"Generate Rig"** in the Armature properties

Rigify produces a rig with FK/IK switching, pole targets, twist bones, facial controls, and custom properties — the kind of rig that takes weeks to build manually. It's the standard recommendation for character animation in Blender.

### Corrective Shape Keys

Even with perfect weight painting, some poses create ugly deformation (the dreaded "candy wrapper" twist on forearms, or collapsing geometry at extreme bends). **Corrective shape keys** (also called corrective blend shapes) are hand-sculpted fixes that activate only at specific bone rotations.

Workflow: pose the bone to the problem angle, sculpt the mesh into the correct shape, save that as a shape key, and drive the shape key's value from the bone's rotation. The `Corrective Smooth` modifier is a cheaper alternative that works well enough for many cases.

### Rigging Gotchas & Best Practices

The failures that cost beginners the most hours:

- **Apply scale and rotation before rigging** (`Ctrl+A` → All Transforms, in Object Mode, on the mesh *and* the armature). **Unapplied scale is the #1 cause of rigs that deform with bizarre offsets, IK that flips, and bones that stretch wrong.** Object-level transforms must be neutral (scale 1,1,1; rotation 0) before you bind.
- **Model in a neutral pose** — a **T-pose** or **A-pose** with limbs held away from the body. Arms pinned to the sides make shoulder and armpit weights impossible to separate.
- **Keep the rest pose clean** — the armature's **rest pose** (Edit-Mode bone positions) is the deformation baseline; Pose Mode layers on top of it non-destructively. Don't "apply" a pose to the rest position unless you mean to rebake the bind.
- **Test the range of motion** before handing off — bend every joint to its extreme, raise the arms overhead, twist the spine, make a fist. Fix weights and add corrective shapes *now*, not after animation starts.
- **Name everything, and name it before you mirror** — `.L`/`.R` discipline pays off across weights, pose flipping, and Rigify. Renaming a rigged skeleton later breaks the vertex-group links.

When in doubt, **use Rigify** and learn by inspecting what it generates — it bakes in most of these practices automatically.

---

## 13. Animation

Animation in Blender means defining how values change over time — positions, rotations, scales, material properties, light intensity, anything with a numeric value can be animated.

### Keyframes — The Foundation

A **[keyframe](https://docs.blender.org/manual/en/latest/animation/keyframes/index.html)** records a value at a specific frame in time. You set a keyframe at frame 1 with the cube at position X=0, and another keyframe at frame 30 with X=5. Blender **interpolates** (fills in) the in-between frames automatically. The cube smoothly slides from 0 to 5 over 30 frames.

Insert a keyframe: select the property, press `I` (or right-click → Insert Keyframe). The hotkey `I` in the viewport opens a menu to keyframe the current selection's location, rotation, scale, or all.

**Auto-keying** (the record button in the timeline) automatically creates keyframes whenever you move, rotate, or scale something. Useful for blocking in poses quickly, dangerous if left on accidentally.

### Keying Sets — What Gets Keyed

Pressing `I` raises the question *which* properties to key. A **keying set** is a saved list of properties so one keypress keys all of them at once — essential for character work, where a single pose touches dozens of bones.

- The **active keying set** is chosen in the timeline header; with one active, `I` keys exactly that set with no menu.
- **"Whole Character"** is the built-in keying set for armatures — it keys every control bone's location/rotation/scale in one stroke, so each pose is a complete, clean keyframe (no half-keyed bones drifting later).
- **Auto-keying** plus **"Only Insert Needed"** (Preferences → Animation) keeps curves tidy by writing a channel only when its value actually changes, instead of keying everything every time.

The discipline that prevents most animation bugs: **key the whole pose at once, on whole frames.** Scattered partial keys on fractional frames are how F-Curves turn to spaghetti.

### The Timeline

The timeline at the bottom of the default layout shows frames horizontally. Orange diamonds are keyframes for the selected object. The playhead (blue line) shows the current frame. Hit `Space` to play.

- **Start/End frame** — defines the playback range
- **Frame rate** — 24 fps (film), 30 fps (TV/web), or custom
- **Keyframe navigation** — `←` / `→` jump to the previous/next keyframe

### The Graph Editor

The Graph Editor is where animation gets precise. It shows **F-Curves** — function curves that plot a value (Y axis) over time (X axis). Each keyframe is a point on the curve, and the shape of the curve between keyframes determines the motion.

**Interpolation modes** control the curve shape:

| Mode | Behavior | Use |
|---|---|---|
| **Bézier** (default) | Smooth ease-in/ease-out with tangent handles | Most animation |
| **Linear** | Straight line between keyframes — constant speed | Mechanical motion |
| **Constant** | Value jumps instantly at the keyframe — no interpolation | On/off switches, visibility toggles |

The tangent handles on Bézier keyframes give you fine control: drag them to create slow-in, slow-out, overshoot, or snap. This is where the *feel* of animation lives. A bouncing ball isn't about the positions — it's about the easing curve.

### F-Curve Handle Types

Bézier keyframes carry **handles** (tangents) whose *type* controls how the curve enters and leaves each key:

| Handle | Behavior |
|---|---|
| **Auto / Auto Clamped** | Blender shapes a smooth curve for you; *Auto Clamped* (the default) prevents overshoot — values won't dip below or above neighboring keys |
| **Vector** | Handle aims straight at the neighboring key — effectively linear on that side |
| **Aligned** | The two handles stay in a straight line — symmetric ease; drag one and the other mirrors |
| **Free** | Each handle moves independently — full manual control for overshoot, snap, or asymmetric ease |

The thing beginners miss: **the curve *is* the motion.** A flat slope is a hold; a steep slope is fast motion; an S-curve is ease-out then ease-in. Reading and shaping slopes — not nudging keyframes — is where animation gets its feel. Auto Clamped is a safe default; switch to **Free** or **Aligned** to deliberately build overshoot and follow-through.

### Extrapolation & Cyclic Motion

By default an F-Curve is **flat before the first key and after the last** (Constant extrapolation) — motion stops dead. To make motion *continue or repeat*:

- **Extrapolation → Linear** (Channel menu) keeps the ending slope going forever — a steady spin or constant drift.
- **F-Curve modifier → Cycles** loops the keyframed range infinitely (*with Offset* to accumulate — a wheel that keeps turning, a walk that keeps walking). This is how a 24-frame cycle plays for a thousand frames.
- Other **F-Curve modifiers** stack procedural motion onto curves: **Noise** (organic jitter — a handheld camera, a flickering light), **Stepped** (preview on N's), **Limits**.

Cyclic curves are the foundation of loops — walk and run cycles, idle breathing, spinning gears, flickering fire.

### The Twelve Principles of Animation

These principles (from Disney's *The Illusion of Life*) are the foundation of all character animation. Blender gives you the tools; these principles tell you how to use them:

1. **Squash and Stretch** — objects deform to show impact and elasticity (a ball flattens on impact)
2. **Anticipation** — preparation before an action (crouch before a jump, wind up before a throw)
3. **Staging** — present the action so the audience reads it clearly
4. **Straight Ahead vs. Pose to Pose** — two workflow approaches (discussed below)
5. **Follow-Through and Overlapping Action** — different parts of the body stop at different times (hair keeps swinging after the head stops)
6. **Slow In, Slow Out** — motion accelerates and decelerates (the Bézier ease curves)
7. **Arcs** — natural motion follows arcs, not straight lines (a hand swings in an arc)
8. **Secondary Action** — supporting motion that adds richness (a character walks *and* swings their arms)
9. **Timing** — the number of frames between poses determines the feel (fewer frames = faster, snappier)
10. **Exaggeration** — push poses beyond reality for clarity and appeal
11. **Solid Drawing** — (translates to 3D as: good posing, balanced weight, clear silhouette)
12. **Appeal** — the character should be interesting to watch

### Pose-to-Pose vs. Straight-Ahead

Two fundamental animation workflows:

- **Pose-to-Pose**: Set key poses first (contact, passing, extreme positions), then fill in breakdowns and in-betweens. This is the standard professional workflow — it gives you control and structure.
- **Straight-Ahead**: Animate frame by frame from start to finish. More spontaneous, good for fluid motion like fire or flowing water, but harder to control timing.

Most character animation uses pose-to-pose. Blender's keyframe system is built for it.

### Blocking, Splining & Polish — The Three Passes

Professional pose-to-pose animation runs in distinct passes, and **the interpolation mode is the tool that separates them**:

1. **Blocking** — set only the storytelling key poses and put the F-Curves on **Constant ("stepped")** interpolation so there's *no* in-betweening. The character snaps from pose to pose like a slideshow, which isolates **acting and timing** from the blur of interpolation — you judge the poses, nothing else.
2. **Splining** — switch to **Bézier**, add breakdowns (the in-between poses that define *how* you travel from A to B), and let the curves connect. The motion becomes continuous; now you fight floatiness.
3. **Polish** — refine curves in the Graph Editor: ease, overshoot, arcs, offsetting body parts for follow-through, and killing the inevitable foot slip.

Skipping blocking is the most common beginner mistake — animating "straight into spline" buries timing problems under smooth curves where they're hard to see and harder to fix.

### Animation Sliders & Pose Tools

Posing isn't only manual rotation — Blender ships **pose-editing operators** (the Pose menu, plus interactive sliders) that pros lean on constantly:

- **Breakdowner** (`Ctrl+E`) — creates an in-between pose interpolated from the previous and next keys; slide to bias it toward either side. The fastest way to make breakdowns.
- **Push / Relax Pose** — exaggerate a pose beyond the surrounding keys, or relax it back toward the interpolated value. Instant "more" or "less."
- **Blend to Neighbor / Blend to Default** — nudge the current pose toward an adjacent key or the rest pose by a percentage.
- **Propagate** — push the current pose forward to later keys (re-plant a hand that drifted across a cycle).

These turn tedious value-tweaking into a few interactive drags, operating on whatever bones you've selected.

### Motion Paths (Onion Skinning)

You can't judge **arcs** — the most-violated animation principle — by scrubbing one frame at a time. **Motion paths** draw the trajectory of an object or bone across a frame range as a line in the viewport, with a dot per frame. Two things become instantly visible:

- **Arc quality** — natural motion curves; a hand or foot tracing a jagged or dead-straight path looks robotic. You tweak until the path is a clean arc.
- **Spacing** — dots bunched together mean slow motion, dots spread apart mean fast. Even spacing reads as mechanical; easing shows up as dots that bunch toward the ends. This is the visual form of "slow in, slow out."

Enable per object (Object properties) or per bone (Armature data → Motion Paths) and **Calculate** the range. It's Blender's equivalent of an animator's onion skinning, and it's how you catch bad arcs before they ship.

### The Dope Sheet

The Dope Sheet shows all keyframes for all animated properties as a grid of diamonds. It's the overview — you see timing relationships across the whole scene. Use it to:

- Shift entire blocks of keyframes in time (select and `G` to move)
- Scale timing (select and `S` — spread keyframes apart or compress them together)
- Copy keyframes between objects or actions

### The NLA Editor (Non-Linear Animation)

The **NLA (Non-Linear Animation) Editor** treats animation like a video editor treats clips. You package keyframe ranges into **actions** (named animation clips), then arrange, layer, blend, and loop them on an NLA track.

Use case: you have a walk cycle (looping), an idle animation, and a wave animation. In the NLA, you lay down the walk cycle, blend into the wave, then back to idle — without manually re-keyframing anything. The NLA is essential for games (where animation states need to blend) and for long-form animation where reusing clips saves weeks of work.

### Actions

An **action** is a named collection of F-Curves — essentially a saved animation clip. By default, every object has one action (its current animation). You can create multiple actions and switch between them, or use them in the NLA.

Actions are data-blocks. If an action has zero users, it gets discarded on save — use the **fake user** (shield icon) to keep actions you want to preserve.

### Drivers

A **driver** is a value that's controlled by an expression or another value instead of keyframes. Examples:

- A gear's rotation driven by another gear's rotation (with a ratio)
- A bone's Y position drives a shape key from 0 to 1
- A custom property slider controls the blend between two materials

Drivers let you create **automated relationships** so the animator doesn't have to keyframe every dependent value manually.

### Shape Keys

**Shape keys** (called blend shapes or morph targets in other software) store alternate versions of a mesh. The **Basis** shape key is the default shape. Additional shape keys define deformed versions. A slider (value 0–1) blends between them.

Primary use: **facial animation**. You create shape keys for each expression — smile, frown, blink, open mouth, raise eyebrows — and animate the sliders to blend between them. Combined with a facial rig (bones for jaw, eyes, brows), shape keys give you fine-grained facial control.

Shape keys can also be driven by bone transforms (a bone's rotation automatically triggers a corrective shape key).

### Worked Example: A Walk Cycle

The walk cycle is the canonical animation exercise because it exercises timing, weight, arcs, overlap, and looping all at once. As a **pose-to-pose, cyclic** animation, it's built from **four key poses** (then mirrored for the other foot, giving a full stride):

```
Contact → Down (recoil) → Passing → Up (high-point) → Contact (other foot) → …
```

1. **Contact** — legs at maximum stride, both feet down, front heel and back toe touching. The extreme pose.
2. **Down / Recoil** — weight drops onto the front foot and the **hips reach their lowest** point as the body absorbs the impact; the knee bends.
3. **Passing** — the free leg passes under the body; the planted leg straightens and the hips begin to rise.
4. **Up / High-point** — the body pushes up over the straight planted leg; **hips at their highest**, about to fall into the next contact.

The layers that sell it:

- **The hips drive everything** — they bob *down* on contact/recoil and *up* on passing/high-point (two bobs per stride) and sway toward the planted foot. Animate the hips first.
- **Arms counter-swing** — the arm opposite the forward leg swings forward for balance; offset its timing a frame or two *behind* the legs for **follow-through**.
- **Foot roll** — the foot isn't rigid: heel strike → flat → toe push-off. A good foot control has a roll for exactly this.
- **Overlap** — head, hands, and any hair or cloth lag slightly behind the body. Nothing stops on the same frame.
- **Make it cyclic** — animate **one stride** (contact to the mirrored contact — roughly 12 frames at 24 fps for a stroll), then add a **Cycles** F-Curve modifier (with offset on the forward-motion channel) to loop it. Animate *in place* and move the root separately, or refining it is nearly impossible.

The classic failure is **foot sliding**: if a planted foot drifts while it should be locked, the contact-to-passing keys aren't holding its position — IK feet and clean keys on the planted frames fix it. Motion paths on the feet make slips obvious.

### Previewing & Reviewing Animation

Scrubbing in the viewport lies — it doesn't play at real speed, and the final render is far too slow to iterate on. To actually *judge* animation:

- **Play at speed** — `Space` plays the timeline; watch the **frame-rate readout**. If it can't hit your fps, set Playback → **Sync → Frame Dropping** so timing stays honest instead of crawling in slow motion.
- **Viewport (OpenGL) render** — *Render → Render Animation* from the **viewport** renders the shaded viewport rather than the full engine (the "playblast"). You get a near-real-time movie to review acting and timing in minutes instead of hours.
- **Add a sound strip** — drop audio into the Video Sequencer or as a Speaker and enable **Sync → AV-sync** to animate against the waveform. Essential for lip-sync and music-driven timing.
- **Review in a loop, at speed, with fresh eyes** — problems invisible while scrubbing jump out the instant it plays back in real time.

### Animation Workflow — Putting It Together

A character animation workflow in Blender typically looks like:

```
1. Character mesh (modeled, UV-mapped, textured)
       ↓
2. Rig (armature + constraints + controls, or Rigify)
       ↓
3. Skin (parent mesh to armature, weight paint)
       ↓
4. Facial rig (shape keys + bone controls for face)
       ↓
5. Block out key poses (Pose Mode, pose-to-pose)
       ↓
6. Timing pass (adjust spacing in the Dope Sheet)
       ↓
7. Refine curves (Graph Editor — ease in/out, overshoots)
       ↓
8. Secondary animation (hair, cloth, props — physics or manual)
       ↓
9. Polish (arcs, follow-through, micro-adjustments)
       ↓
10. Light, render, composite
```

---

## 14. Geometry Nodes

### The Concept

[Geometry Nodes](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/index.html) is Blender's **procedural geometry system** — a visual node graph where you generate, modify, and assemble geometry using math and logic instead of manual modeling. It's Blender's answer to Houdini's procedural approach.

Instead of manually placing 500 trees, you build a node tree that scatters points on a surface, instances a tree mesh at each point, randomizes scale/rotation, and removes points on steep slopes. Change the terrain → the trees automatically update.

### How It Works

A Geometry Nodes modifier reads the object's geometry as input, pipes it through a node graph, and outputs modified geometry. Nodes process **geometry**, **attributes** (per-vertex/per-face/per-point data), **values**, and **fields** (functions that evaluate per-element).

Key node categories:

| Category | Examples | Purpose |
|---|---|---|
| **Mesh Primitives** | Grid, Cube, UV Sphere, Cone | Generate basic shapes |
| **Curve Primitives** | Line, Circle, Spiral | Generate curves |
| **Instances** | Instance on Points, Realize Instances | Scatter and duplicate objects efficiently |
| **Geometry** | Join Geometry, Set Position, Transform | Combine and transform geometry |
| **Mesh Operations** | Subdivide, Extrude, Bevel | Modify mesh topology |
| **Point/Distribute** | Distribute Points on Faces, Points | Scatter points for instancing |
| **Attribute** | Store Named Attribute, Attribute Statistics | Read/write per-element data |
| **Math/Vector** | Math, Vector Math, Map Range | Numeric computation |
| **Utilities** | Random Value, Index, Switch | Logic and randomness |
| **Input** | Position, Normal, Object Info | Read context data |

### Why It Matters

Geometry Nodes is the fastest-growing part of Blender. It enables:

- **Procedural scattering** — distribute rocks, plants, debris across terrain
- **Parametric modeling** — buildings, furniture, mechanical parts from sliders
- **Motion graphics** — animated abstract geometry
- **Simulation** — custom particle-like systems
- **Procedural animation** — geometry that animates itself based on rules

If you come from a programming background, Geometry Nodes will feel natural — it's functional programming for geometry.

---

## 15. Particles & Physics

### Particle Systems

Blender has two particle system types:

- **Emitter** — particles are born, live, and die. Think sparks, rain, snow, fire embers, dust. Particles can be affected by gravity, wind, turbulence, and collisions.
- **Hair** — long-lived strands that don't move (or move only via physics). Used for hair, fur, grass, feathers.

Each particle can be rendered as a point, a line, a path, or an **instance of another object** (a leaf, a rock, a bird).

### Physics Simulations

Blender includes several physics simulation systems:

| System | Simulates | Use |
|---|---|---|
| **Rigid Body** | Solid objects that collide, fall, stack | Destruction, dominos, machinery |
| **Soft Body** | Deformable objects | Jelly, bouncing, soft impact |
| **Cloth** | Fabric simulation | Clothing, curtains, flags, tablecloths |
| **Fluid** | Liquid and gas | Water, smoke, fire, explosions |
| **Dynamic Paint** | Surface interaction | Footprints in snow, paint splatter, ripples |

Physics simulations are **baked** — calculated once and cached to disk. You set up the scene, hit "Bake," wait, then play back the result. Tweaking requires re-baking.

### The Blender Simulation Mindset

Physics in Blender is **approximate and art-directed**, not engineering simulation. The goal is to look right, not be physically correct. You'll constantly trade accuracy for speed and use manual keyframing to override simulation results when the physics doesn't produce the motion you want.

---

## 16. Compositing & Post-Processing

### The Compositor

Blender's Compositor is a **node-based image processing system** that runs on rendered images. It's the same concept as Nuke or After Effects' layer system — you take the rendered image and apply effects, corrections, and combinations.

Common compositing operations:

| Node | Purpose |
|---|---|
| **Color Balance / Color Correction** | Adjust lift, gamma, gain (shadows, midtones, highlights) |
| **Glare** | Bloom, streaks, fog glow |
| **Blur** | Gaussian, bokeh, or directional blur |
| **Lens Distortion** | Simulate real lens barrel/pincushion distortion |
| **Mix** | Combine two images (add, multiply, screen, overlay) |
| **Alpha Over** | Layer images with transparency |
| **Cryptomatte** | Select objects/materials in compositing by ID |
| **Denoise** | Clean up noisy Cycles renders |
| **Vignette** (via Ellipse Mask + Mix) | Darken edges of frame |

### Render Passes

Instead of rendering one final image, you can output individual **render passes** — separate layers of information:

- **Combined** — the final image
- **Diffuse** / **Glossy** / **Transmission** — separated by shader type
- **Emission** — glowing objects only
- **Shadow** — shadow information only
- **AO** — ambient occlusion
- **Z Depth** — distance from camera per pixel (for depth-of-field or fog in post)
- **Normal** — surface normals (for relighting in post)
- **Object/Material Index** — ID masks for selecting objects in compositing

Rendering to passes gives you maximum flexibility to adjust the look after rendering, without re-rendering. Output these as **OpenEXR multilayer** files.

---

## 17. Video Editing

### The Video Sequencer

Blender includes a **Video Sequence Editor (VSE)** — a multi-track, non-linear video editor. It handles:

- Importing video, audio, and image sequences
- Cutting, trimming, and rearranging clips
- Transitions (cross, wipe, etc.)
- Speed control (slow motion, time remapping)
- Color correction
- Text overlays
- Mixing audio tracks
- Rendering to video formats (FFmpeg)

The VSE is capable enough for YouTube production and short films. For complex projects with many effects, dedicated software (DaVinci Resolve, Premiere) has a deeper toolset, but for self-contained Blender projects — where you render 3D shots and edit them together — the VSE keeps everything in one file.

---

## 18. Add-ons & Scripting

### Add-ons

Blender has a rich ecosystem of add-ons (plugins). Many ship bundled but disabled — enable them in Preferences → Add-ons. Notable built-in add-ons:

| Add-on | Purpose |
|---|---|
| **Rigify** | Auto-generates full character rigs from templates |
| **Node Wrangler** | Essential keyboard shortcuts for node editing (Ctrl+Shift+click to preview a node) |
| **LoopTools** | Additional mesh editing tools (circle, relax, bridge, flatten) |
| **Bool Tool** | Fast boolean operations for hard-surface modeling |
| **Import Images as Planes** | Import reference images as textured planes |
| **A.N.T. Landscape** | Procedural terrain generation |
| **Mesh: Extra Objects** | Additional mesh primitives |
| **Sapling Tree Gen** | Procedural tree generation |

Third-party add-ons from the **Blender Extensions Platform** or individual developers extend Blender further — hard-surface kits, auto-retopology tools, advanced UV tools, asset libraries, etc.

### Python Scripting

Blender is fully scriptable via Python. The [`bpy`](https://docs.blender.org/api/current/) module exposes the entire data model and operator system. Use cases:

- **Automation** — batch-rename objects, batch-export, generate reports
- **Custom tools** — operators accessible from menus or hotkeys
- **Procedural generation** — create geometry programmatically
- **Pipeline integration** — import/export scripts for studio pipelines

Every action you take in the Blender UI is logged as a Python command in the **Info** editor. This makes learning the API straightforward — do something in the UI, then read the Python equivalent.

---

## 19. File Management & Production Workflows

### The .blend File

A `.blend` file is self-contained by default — everything is embedded: meshes, textures, animations, render settings, even the UI layout. This is convenient but creates large files.

For production work, you typically use **external textures** and reference them from the `.blend`. The "Pack All Into .blend" option (File → External Data) embeds external files for portability.

### Linking & Appending

- **Append** — copies a data-block from another `.blend` file into the current file. The copy is independent — changes to the original don't propagate.
- **Link** — creates a live reference to a data-block in another `.blend` file. The linked data is read-only but stays in sync. If the original changes, the link updates on reload.

Linking is how studios manage large projects: characters are built in dedicated `.blend` files and linked into shot files. The character department updates the rig, and every shot file picks up the change.

### Library Overrides

When you link an object, it's read-only. **Library overrides** (the replacement for the old proxy system) let you override specific properties of linked data — for example, link a character rig but override the pose (so you can animate it in the shot file while the rig definition stays linked).

### Asset Library

Blender's **Asset Browser** (3.0+) lets you mark any data-block as an asset — materials, objects, collections, node groups, poses, worlds. Assets are browsable from a palette and can be drag-and-dropped into scenes. You can define asset libraries from local folders for team-shared resources.

### Export Formats

| Format | Use Case |
|---|---|
| **FBX** | Game engines (Unity, Unreal), other 3D apps. Supports mesh, materials (partial), armature, animation |
| **glTF/GLB** | Web, real-time 3D, PBR-standard materials. The modern interchange format |
| **OBJ** | Legacy interchange. Mesh + UVs + materials only. No animation |
| **USD** | Pixar's Universal Scene Description. The emerging industry standard for complex scenes |
| **Alembic (.abc)** | Baked animation/simulation data. Good for heavy simulations |
| **STL** | 3D printing. Mesh only, no color or material |
| **Collada (.dae)** | Older interchange format. Declining use |

---

## 20. Where to Go Next

- **Keep the [Blender Manual](https://docs.blender.org/manual/en/latest/) open while you work** — it is genuinely good, and every section of this guide maps to a manual chapter with the parameter-level detail this guide deliberately omits.
- **Do the donut.** Blender Guru's beginner tutorial series (the famous donut) remains the best guided first project — it walks modeling → materials → lighting → rendering in order, and millions of people learned Blender through it.
- **Study production files from [Blender Studio](https://studio.blender.org/)** — the open-movie project files (rigs, scenes, node setups) are the closest thing to reading production source code, and the training courses (especially on rigging and animation) are made by the artists who build Blender's own films.
- **Animate a walk cycle and build one Geometry Nodes setup** — the two exercises in this guide with the highest skill-per-hour return; both force the graph editor and the node mindset to become real.
- **Script something with [`bpy`](https://docs.blender.org/api/current/)** — batch-rename, batch-export, anything; the Info editor shows the Python for every UI action, so the API teaches itself.
- **Adjacent guides in this repo:** [WebGL/OpenGL](WEBGL_OPENGL_STUDY_GUIDE.md) and [WebGPU](WEBGPU_STUDY_GUIDE.md) (what a renderer actually does under the hood — Cycles and EEVEE will make more sense), and [Advanced Python](ADVANCED_PYTHON_STUDY_GUIDE.md) (for serious `bpy` scripting).

---

## 21. Mastery Checklist

### Fundamentals
- [ ] Navigate the 3D viewport fluently (orbit, pan, zoom, numpad views)
- [ ] Understand the mode system — switch between Object, Edit, Sculpt, Pose, Weight Paint confidently
- [ ] Add, delete, select, transform objects and geometry with hotkeys
- [ ] Organize scenes with collections
- [ ] Use the F3 search to find any operator

### Modeling
- [ ] Model a hard-surface object (furniture, prop) from a cube using extrude, inset, bevel, loop cut
- [ ] Understand and maintain clean quad topology
- [ ] Use Mirror and Subdivision Surface modifiers non-destructively
- [ ] Use Boolean operations for hard-surface details
- [ ] Recalculate normals and use Auto Smooth

### Materials & Texturing
- [ ] Build a PBR material using Principled BSDF with texture maps
- [ ] UV-unwrap a model with proper seams and minimal stretching
- [ ] Use procedural textures (Noise, Voronoi) for surface variation
- [ ] Mix materials using a Mix Shader or node math

### Lighting & Rendering
- [ ] Set up three-point lighting
- [ ] Use an HDRI for environment lighting
- [ ] Understand the difference between EEVEE and Cycles and choose appropriately
- [ ] Configure render settings (samples, denoising, color management, output format)
- [ ] Render an animation as an image sequence

### Rigging
- [ ] Build a simple bone chain and parent a mesh to it
- [ ] Name bones `.L`/`.R` and use X-Axis Mirror and Symmetrize
- [ ] Understand vertex groups, weight painting, and mirroring weights
- [ ] Distinguish deform bones from control bones in a rig
- [ ] Set up an IK chain with a pole target and FK/IK switching
- [ ] Use bone constraints (IK, Copy Rotation, Limit Rotation) and understand influence/space
- [ ] Use Bendy Bones or Spline IK for a tail or spine
- [ ] Give controls custom shapes and organize them on bone collections
- [ ] Apply scale before rigging and test the full range of motion
- [ ] Use Rigify to auto-generate a character rig

### Animation
- [ ] Keyframe an object's transform and adjust timing in the Dope Sheet
- [ ] Key whole poses with the "Whole Character" keying set
- [ ] Edit F-Curves and handle types in the Graph Editor for proper easing
- [ ] Block in stepped, then spline, then polish
- [ ] Loop motion with a cyclic F-Curve modifier
- [ ] Use motion paths to fix arcs and spacing
- [ ] Create shape keys and animate them
- [ ] Use the NLA Editor to blend animation actions
- [ ] Animate a walk cycle (pose-to-pose, cyclic)

### Advanced
- [ ] Build a procedural effect with Geometry Nodes
- [ ] Run a cloth or rigid body simulation
- [ ] Use the Compositor for color correction and glare
- [ ] Write a simple Python script using `bpy`
- [ ] Link assets from an external `.blend` and use library overrides
