# WebGL and OpenGL Study Guide

A depth-first guide to the GL family of graphics APIs for engineers who know JavaScript and the web platform but want to understand the older OpenGL mental model that still sits underneath a huge amount of real graphics work. The guide uses WebGL as the teaching environment because it runs in the browser, has a small setup surface, and exposes the OpenGL ES style API directly. The goal is not merely to learn "browser 3D." The goal is to learn the concepts behind OpenGL, OpenGL ES, WebGL, and many engine abstractions: the rendering pipeline, global state, buffers, attributes, uniforms, textures, framebuffers, depth, blending, instancing, extensions, debugging, and performance.

The throughline is this: **WebGL is OpenGL ES in the browser, and OpenGL is a state machine for feeding a programmable rasterization pipeline**. You bind objects to targets, mutate context state, upload data, choose shaders, describe vertex layouts, and issue draw calls. The GPU then runs vertex shaders, assembles primitives, rasterizes them into fragments, runs fragment shaders, tests depth and stencil, blends with the framebuffer, and presents pixels.

This guide pairs naturally with the [WebGPU guide](WEBGPU_STUDY_GUIDE.md), [TypeScript guide](TYPESCRIPT_STUDY_GUIDE.md), [Advanced Node.js guide](ADVANCED_NODEJS_STUDY_GUIDE.md), [C++26 and Modern C++ guide](CPP26_STUDY_GUIDE.md), and [ESP32 guide](ESP32_STUDY_GUIDE.md). WebGL is a web API, but the concepts are systems concepts: memory layout, data transfer, parallel execution, driver overhead, synchronization, numeric precision, and hardware-shaped tradeoffs.

Primary references: [MDN WebGL API](https://developer.mozilla.org/en-US/docs/Web/API/WebGL_API), the [WebGL 1.0 specification](https://registry.khronos.org/webgl/specs/latest/1.0/), the [WebGL 2.0 specification](https://registry.khronos.org/webgl/specs/latest/2.0/), [OpenGL ES 2.0 specification](https://registry.khronos.org/OpenGL/specs/es/2.0/es_full_spec_2.0.pdf), [OpenGL ES 3.0 specification](https://registry.khronos.org/OpenGL/specs/es/3.0/es_spec_3.0.pdf), [Khronos OpenGL wiki](https://www.khronos.org/opengl/wiki/), [WebGL Fundamentals](https://webglfundamentals.org/), [WebGL2 Fundamentals](https://webgl2fundamentals.org/), and [LearnOpenGL](https://learnopengl.com/).

---

## Table of Contents

1. [Part 1 - What GL Is](#part-1-what-gl-is)
2. [Part 2 - WebGL, OpenGL, and OpenGL ES](#part-2-webgl-opengl-and-opengl-es)
3. [Part 3 - The GL State Machine](#part-3-the-gl-state-machine)
4. [Part 4 - The Rendering Pipeline](#part-4-the-rendering-pipeline)
5. [Part 5 - GLSL ES: The Shader Language](#part-5-glsl-es-the-shader-language)
6. [Part 6 - Your First WebGL App](#part-6-your-first-webgl-app)
7. [Part 7 - Buffers, Attributes, Uniforms, and VAOs](#part-7-buffers-attributes-uniforms-and-vaos)
8. [Part 8 - Matrices, Coordinates, and Cameras](#part-8-matrices-coordinates-and-cameras)
9. [Part 9 - Textures, Samplers, and Pixel Data](#part-9-textures-samplers-and-pixel-data)
10. [Part 10 - Framebuffers, Render Targets, and Post-Processing](#part-10-framebuffers-render-targets-and-post-processing)
11. [Part 11 - Depth, Stencil, Blending, and Transparency](#part-11-depth-stencil-blending-and-transparency)
12. [Part 12 - Performance, Debugging, and Production Practices](#part-12-performance-debugging-and-production-practices)
13. [Part 13 - Ecosystem, OpenGL Mapping, and Recipes](#part-13-ecosystem-opengl-mapping-and-recipes)

---

## Part 1 - What GL Is

GL is a family of low-level graphics APIs designed around rasterization. Rasterization means turning geometric primitives, usually triangles, into pixels. You send vertex data and shader programs to the GPU, configure a large set of rendering state, and ask the GPU to draw.

If you have used the web platform for years, place WebGL in this family:

| API | What it gives you |
|---|---|
| Canvas 2D | Immediate-mode 2D drawing from JavaScript |
| SVG | Declarative vector graphics in the DOM |
| CSS transforms/filters | Browser-managed visual effects |
| WebGL | Low-level GPU rasterization through OpenGL ES |
| WebGPU | Modern explicit rendering and compute |

OpenGL and WebGL are not scene graphs, game engines, model loaders, or UI frameworks. They do not know what a camera, mesh, material, sprite, or light is. Those are engine concepts built on top of GL.

### The One-Sentence Version

GL is a stateful API for configuring a programmable pipeline that transforms vertices into fragments and writes those fragments into a framebuffer.

### Why GL Matters

OpenGL is older than the modern web, but it still matters because the mental model spread everywhere:

- WebGL is based on OpenGL ES.
- OpenGL ES shaped mobile graphics for years.
- Many engines still expose GL concepts even when their backend is Metal, Vulkan, Direct3D, or WebGPU.
- Shader programming, buffers, textures, depth testing, blending, and framebuffers remain core graphics ideas.
- Legacy and embedded systems often still use GL or GLES directly.

Even when you later move to WebGPU, Vulkan, Metal, or Direct3D 12, learning GL gives you the vocabulary of GPU rasterization. WebGPU changes the API shape. It does not erase the pipeline.

### The Central Mental Model

Most GL work follows this pattern:

1. Create GPU objects.
2. Bind an object to a target.
3. Fill that object with data.
4. Compile and link shader programs.
5. Tell GL how to read vertex data.
6. Set global state such as viewport, depth test, blend mode, and culling.
7. Bind textures and uniforms.
8. Issue a draw call.

The thing that surprises new users is that many calls act on "whatever object is currently bound." This is the source of both GL's convenience and its pain.

```javascript
gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
gl.bufferData(gl.ARRAY_BUFFER, positions, gl.STATIC_DRAW);
```

`bufferData` does not receive `positionBuffer` directly. It modifies the buffer currently bound to `ARRAY_BUFFER`.

### Immediate Mode vs Modern GL

Old desktop OpenGL had immediate mode:

```c
glBegin(GL_TRIANGLES);
glVertex3f(0.0f, 1.0f, 0.0f);
glVertex3f(-1.0f, -1.0f, 0.0f);
glVertex3f(1.0f, -1.0f, 0.0f);
glEnd();
```

That style is gone from WebGL and modern OpenGL practice. WebGL starts you in the programmable era. You use buffers and shaders from the beginning.

The important shift:

| Old idea | Modern idea |
|---|---|
| Fixed-function transform and lighting | Vertex and fragment shaders |
| Per-vertex calls | Buffer objects |
| Matrix stack | Your own matrices in uniforms |
| Built-in lights/materials | Your own lighting code |
| Hidden global defaults | Explicit shader inputs and state setup |

This guide teaches the modern style.

---

## Part 2 - WebGL, OpenGL, and OpenGL ES

WebGL is not exactly desktop OpenGL. It is a web-safe API derived from OpenGL ES.

### The Family Tree

| API | Environment | Notes |
|---|---|---|
| OpenGL | Desktop/native | Long-lived cross-platform graphics API |
| OpenGL ES | Embedded/mobile | Smaller profile for phones, tablets, embedded devices |
| WebGL 1 | Browser | Based on OpenGL ES 2.0 |
| WebGL 2 | Browser | Based on OpenGL ES 3.0 |

WebGL removes unsafe features, defines stricter behavior, integrates with browser security rules, and runs through browser GPU process architecture. But the programming model is very close to OpenGL ES.

### WebGL 1 vs WebGL 2

WebGL 1 is the broader baseline. WebGL 2 adds many features that make the API feel closer to a modern, comfortable GL:

| Feature | WebGL 1 | WebGL 2 |
|---|---|---|
| Base | OpenGL ES 2.0 | OpenGL ES 3.0 |
| Shader version | GLSL ES 1.00 | GLSL ES 3.00 |
| Vertex array objects | Extension | Core |
| Instanced drawing | Extension | Core |
| Multiple render targets | Extension | Core |
| 3D textures | No | Yes |
| Integer textures | Limited | Better |
| Transform feedback | No | Yes |
| Uniform buffer objects | No | Yes |
| Sync objects | No | Yes |

Use WebGL 2 when you can. Keep WebGL 1 in mind when maximum reach matters.

### Browser Reality

WebGL has broad browser support, but it still has constraints:

- It requires a canvas.
- It may be disabled by browser, driver, GPU blocklist, enterprise policy, or privacy settings.
- Resources can be lost through context loss.
- Cross-origin images and videos must satisfy CORS rules before they can be sampled safely.
- Precision and extension availability vary.

Always detect support:

```javascript
const canvas = document.querySelector('canvas');
const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');

if (!gl) {
  showFallback();
}
```

### How WebGL Differs From Native OpenGL

Native OpenGL code usually runs in a process that talks to the driver. WebGL code runs in a browser tab. That changes the risk model.

WebGL validates aggressively because the browser cannot let shader code or malformed buffers read arbitrary memory or crash the system. Many errors that native GL drivers might tolerate are rejected or sanitized in WebGL.

Key differences:

- WebGL has no client-side vertex arrays. Vertex data lives in buffers.
- WebGL initializes resources more strictly to avoid data leaks.
- WebGL restricts texture usage until images are complete and origin-clean.
- WebGL exposes extensions through `getExtension`, not through arbitrary driver entry points.
- WebGL context loss is a normal event your app should handle.

### WebGL vs WebGPU

WebGL is the older global-state model. WebGPU is the newer explicit model.

| Dimension | WebGL | WebGPU |
|---|---|---|
| Heritage | OpenGL ES | Vulkan/Metal/D3D12 |
| State | Mutable context state | Pipeline and bind objects |
| Shader language | GLSL ES | WGSL |
| Compute | No true compute shaders | Compute shaders |
| Binding model | Attributes, uniforms, texture units | Bind groups |
| Command model | Immediate calls | Recorded command buffers |
| Reach | Very broad | Modern and growing |
| Best use | Portable graphics, legacy reach, learning GL | Modern engines, compute, explicit control |

The APIs differ, but the drawing ideas carry over: vertices, primitives, textures, render targets, depth, blending, and shader stages.

---

## Part 3 - The GL State Machine

GL is often described as a state machine. That is not an insult. It is the main fact you must internalize.

### Binding Targets

Objects are not usually passed directly to every call. Instead, you bind them to named targets.

```javascript
const buffer = gl.createBuffer();
gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([0, 0, 1, 0, 0, 1]), gl.STATIC_DRAW);
```

Targets include:

| Target | Meaning |
|---|---|
| `gl.ARRAY_BUFFER` | Vertex attribute data |
| `gl.ELEMENT_ARRAY_BUFFER` | Index data |
| `gl.TEXTURE_2D` | 2D texture binding |
| `gl.FRAMEBUFFER` | Offscreen or onscreen render target binding |
| `gl.RENDERBUFFER` | Render-only image storage |
| `gl.VERTEX_ARRAY` | Vertex input state in WebGL 2 |

The phrase "current binding" appears constantly in GL documentation. Current bindings are hidden inputs to later calls.

### Enable Bits

Some state is toggled:

```javascript
gl.enable(gl.DEPTH_TEST);
gl.enable(gl.CULL_FACE);
gl.disable(gl.BLEND);
```

Common enable bits:

| State | Effect |
|---|---|
| `DEPTH_TEST` | Reject fragments behind existing depth |
| `BLEND` | Combine new fragment color with existing color |
| `CULL_FACE` | Skip back-facing or front-facing triangles |
| `SCISSOR_TEST` | Restrict drawing to a rectangle |
| `STENCIL_TEST` | Use stencil buffer tests and writes |

These are global to the context. If one rendering path enables blending and forgets to disable it, another path may render incorrectly.

### Draw State

A draw call depends on many pieces of state:

- current program,
- current framebuffer,
- current viewport,
- current vertex array or attribute setup,
- bound index buffer,
- active textures and samplers,
- uniform values,
- depth/stencil/blend/cull settings,
- color/depth/stencil write masks.

That means this innocent call:

```javascript
gl.drawArrays(gl.TRIANGLES, 0, 3);
```

is only meaningful if all required state has already been configured.

### State Leaks

GL state leaks are a major source of bugs. A state leak happens when code changes context state and later code assumes the old state still exists.

Bad pattern:

```javascript
function drawTransparentThing() {
  gl.enable(gl.BLEND);
  gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
  gl.drawArrays(gl.TRIANGLES, 0, 6);
}
```

This may break later opaque drawing because blending remains enabled.

Better pattern:

```javascript
function drawTransparentThing() {
  gl.enable(gl.BLEND);
  gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
  gl.drawArrays(gl.TRIANGLES, 0, 6);
  gl.disable(gl.BLEND);
}
```

Large renderers usually go further: they centralize state changes in a renderer object, sort draw calls by material, and track cached state so they only call GL when state actually changes.

### Objects vs State

GL has object handles:

- buffers,
- textures,
- programs,
- shaders,
- framebuffers,
- renderbuffers,
- vertex arrays,
- queries,
- sync objects.

But objects still interact with context state. For example, a texture object stores image levels and parameters, but the active texture unit decides which texture the current shader sampler will read.

### The Debugging Rule

When a GL program draws nothing, ask:

1. Is the canvas size and viewport correct?
2. Is the program linked and in use?
3. Are attribute locations enabled and pointing at the right buffers?
4. Are uniforms set after linking and before drawing?
5. Is the primitive inside clip space?
6. Is depth, culling, stencil, scissor, or blending hiding the result?
7. Is the framebuffer complete?
8. Did `gl.getError()` report anything earlier?

Most bugs are wrong state, wrong data layout, or wrong coordinates.

---

## Part 4 - The Rendering Pipeline

The GL pipeline is the conceptual spine of the API.

### Pipeline Overview

For a simple draw:

```text
vertex buffers
  -> vertex shader
  -> primitive assembly
  -> clipping
  -> rasterization
  -> fragment shader
  -> depth/stencil tests
  -> blending
  -> framebuffer
```

You control parts of this pipeline with shaders and parts with fixed-function state.

### Vertices

A vertex is not necessarily a position. A vertex is one logical record of input data. It may contain:

- position,
- normal,
- color,
- texture coordinates,
- tangent,
- bone indices,
- bone weights,
- instance data.

In WebGL, vertex data is usually stored in typed arrays and uploaded into buffers.

```javascript
const vertices = new Float32Array([
  // x, y, r, g, b
   0.0,  0.8, 1.0, 0.0, 0.0,
  -0.8, -0.8, 0.0, 1.0, 0.0,
   0.8, -0.8, 0.0, 0.0, 1.0,
]);
```

### Vertex Shader

The vertex shader runs once per vertex. Its required job is to write clip-space position.

```glsl
attribute vec2 a_position;
attribute vec3 a_color;

varying vec3 v_color;

void main() {
  v_color = a_color;
  gl_Position = vec4(a_position, 0.0, 1.0);
}
```

In WebGL 2:

```glsl
#version 300 es
in vec2 a_position;
in vec3 a_color;

out vec3 v_color;

void main() {
  v_color = a_color;
  gl_Position = vec4(a_position, 0.0, 1.0);
}
```

### Primitive Assembly

After vertex shading, GL groups vertices into primitives.

Common modes:

| Mode | Meaning |
|---|---|
| `POINTS` | Each vertex is a point |
| `LINES` | Each pair is a line |
| `LINE_STRIP` | Connected line chain |
| `TRIANGLES` | Each group of three vertices is a triangle |
| `TRIANGLE_STRIP` | Connected triangle strip |
| `TRIANGLE_FAN` | Fan around first vertex |

Triangles are the normal primitive for real rendering. GPUs are built around triangles.

### Clip Space and NDC

`gl_Position` is in clip space. After the vertex shader, GL divides by `w`:

```text
ndc = clip.xyz / clip.w
```

Normalized device coordinates are visible when:

```text
-1 <= x <= 1
-1 <= y <= 1
-1 <= z <= 1
```

WebGL follows OpenGL's clip-space depth range of `-1..1`. This differs from WebGPU and Direct3D style APIs, which use `0..1`.

### Rasterization

Rasterization converts primitives into fragments. A fragment is a candidate pixel result. It has interpolated values from the vertex shader.

If one vertex has red, one green, and one blue, the fragment shader receives interpolated colors across the triangle.

```glsl
precision mediump float;

varying vec3 v_color;

void main() {
  gl_FragColor = vec4(v_color, 1.0);
}
```

### Fragment Shader

The fragment shader decides the output color. It can sample textures, compute lighting, discard fragments, and output color values.

In WebGL 2:

```glsl
#version 300 es
precision highp float;

in vec3 v_color;
out vec4 outColor;

void main() {
  outColor = vec4(v_color, 1.0);
}
```

### Per-Fragment Operations

After the fragment shader, fixed-function tests and operations happen:

- scissor test,
- stencil test,
- depth test,
- blending,
- dithering,
- color write mask.

These are not shader code, but they strongly affect the result.

### Framebuffer

The framebuffer is the destination for rendering. The default framebuffer is the canvas. Custom framebuffers let you render into textures for shadow maps, post-processing, picking, deferred rendering, and intermediate passes.

---

## Part 5 - GLSL ES: The Shader Language

WebGL shaders use GLSL ES, the OpenGL ES shading language.

### WebGL 1 Shader Basics

WebGL 1 uses GLSL ES 1.00.

Vertex shader:

```glsl
attribute vec2 a_position;
attribute vec2 a_uv;

uniform mat4 u_matrix;

varying vec2 v_uv;

void main() {
  v_uv = a_uv;
  gl_Position = u_matrix * vec4(a_position, 0.0, 1.0);
}
```

Fragment shader:

```glsl
precision mediump float;

uniform sampler2D u_texture;

varying vec2 v_uv;

void main() {
  gl_FragColor = texture2D(u_texture, v_uv);
}
```

Important keywords:

| Keyword | Meaning |
|---|---|
| `attribute` | Per-vertex input to vertex shader |
| `uniform` | Constant value for a draw call |
| `varying` | Interpolated value from vertex to fragment shader |
| `precision` | Default numeric precision |
| `sampler2D` | Texture sampler type |

### WebGL 2 Shader Basics

WebGL 2 uses GLSL ES 3.00 when the shader begins with `#version 300 es`.

```glsl
#version 300 es
in vec2 a_position;
in vec2 a_uv;

uniform mat4 u_matrix;

out vec2 v_uv;

void main() {
  v_uv = a_uv;
  gl_Position = u_matrix * vec4(a_position, 0.0, 1.0);
}
```

```glsl
#version 300 es
precision highp float;

uniform sampler2D u_texture;

in vec2 v_uv;
out vec4 outColor;

void main() {
  outColor = texture(u_texture, v_uv);
}
```

Changes from WebGL 1:

- `attribute` becomes `in`.
- `varying` becomes `out` in vertex shaders and `in` in fragment shaders.
- `gl_FragColor` is replaced by user-defined output variables.
- `texture2D` becomes `texture`.

### Types

Common GLSL types:

| Type | Meaning |
|---|---|
| `float`, `int`, `bool` | Scalars |
| `vec2`, `vec3`, `vec4` | Float vectors |
| `ivec2`, `ivec3`, `ivec4` | Integer vectors |
| `mat3`, `mat4` | Matrices |
| `sampler2D`, `samplerCube` | Texture samplers |

Vector swizzling is common:

```glsl
vec4 color = vec4(0.2, 0.4, 0.8, 1.0);
vec3 rgb = color.rgb;
vec2 yx = color.yx;
```

### Precision

Fragment shaders in WebGL require precision declarations for floats:

```glsl
precision mediump float;
```

Common choices:

| Precision | Use |
|---|---|
| `lowp` | Colors or small values when acceptable |
| `mediump` | Many mobile-friendly fragment calculations |
| `highp` | Coordinates, lighting, physically sensitive math |

Use `highp` when correctness requires it, but remember that old mobile GPUs may have weaker support or performance for high precision in fragment shaders.

### Uniforms

Uniforms are values that remain constant across one draw call.

```javascript
const matrixLocation = gl.getUniformLocation(program, 'u_matrix');
gl.useProgram(program);
gl.uniformMatrix4fv(matrixLocation, false, matrix);
```

Uniform calls are typed:

| JavaScript call | GLSL type |
|---|---|
| `uniform1f` | `float` |
| `uniform2f` | `vec2` |
| `uniform3fv` | `vec3` or array of `vec3` |
| `uniformMatrix4fv` | `mat4` |
| `uniform1i` | `int`, `bool`, sampler texture unit |

Sampler uniforms are integers naming texture units.

### Varyings and Interpolation

Varyings carry data from vertex shader to fragment shader. GL interpolates them across the primitive.

```glsl
// vertex
varying vec2 v_uv;
v_uv = a_uv;

// fragment
varying vec2 v_uv;
vec4 texel = texture2D(u_texture, v_uv);
```

This is why texture coordinates work: each fragment receives a different interpolated UV.

### Common Shader Mistakes

- Forgetting `precision mediump float;` in fragment shaders.
- Using WebGL 2 syntax in WebGL 1.
- Mismatching varying names or types between stages.
- Thinking uniforms change per vertex. They do not.
- Doing expensive branches or loops in fragment shaders without measuring.
- Letting values go outside expected ranges and creating NaNs.
- Forgetting that texture coordinate origin conventions differ between sources.

---

## Part 6 - Your First WebGL App

This part builds the smallest useful WebGL renderer: draw a colored triangle.

### HTML

```html
<canvas id="gl" width="640" height="360"></canvas>
<script type="module" src="./main.js"></script>
```

### Get the Context

```javascript
const canvas = document.querySelector('#gl');
const gl = canvas.getContext('webgl');

if (!gl) {
  throw new Error('WebGL is not supported.');
}
```

### Compile Shaders

```javascript
function compileShader(gl, type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);

  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(shader);
    gl.deleteShader(shader);
    throw new Error(log);
  }

  return shader;
}
```

### Link a Program

```javascript
function createProgram(gl, vertexSource, fragmentSource) {
  const vertexShader = compileShader(gl, gl.VERTEX_SHADER, vertexSource);
  const fragmentShader = compileShader(gl, gl.FRAGMENT_SHADER, fragmentSource);

  const program = gl.createProgram();
  gl.attachShader(program, vertexShader);
  gl.attachShader(program, fragmentShader);
  gl.linkProgram(program);

  gl.deleteShader(vertexShader);
  gl.deleteShader(fragmentShader);

  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    const log = gl.getProgramInfoLog(program);
    gl.deleteProgram(program);
    throw new Error(log);
  }

  return program;
}
```

### Shader Sources

```javascript
const vertexSource = `
attribute vec2 a_position;
attribute vec3 a_color;

varying vec3 v_color;

void main() {
  v_color = a_color;
  gl_Position = vec4(a_position, 0.0, 1.0);
}
`;

const fragmentSource = `
precision mediump float;

varying vec3 v_color;

void main() {
  gl_FragColor = vec4(v_color, 1.0);
}
`;
```

### Upload Vertex Data

```javascript
const vertices = new Float32Array([
  // x, y, r, g, b
   0.0,  0.8, 1.0, 0.0, 0.0,
  -0.8, -0.8, 0.0, 1.0, 0.0,
   0.8, -0.8, 0.0, 0.0, 1.0,
]);

const vertexBuffer = gl.createBuffer();
gl.bindBuffer(gl.ARRAY_BUFFER, vertexBuffer);
gl.bufferData(gl.ARRAY_BUFFER, vertices, gl.STATIC_DRAW);
```

`STATIC_DRAW` is a usage hint. It means "I expect to upload this data rarely and draw from it many times." It does not make the buffer immutable.

### Describe Attribute Layout

```javascript
const program = createProgram(gl, vertexSource, fragmentSource);
const positionLocation = gl.getAttribLocation(program, 'a_position');
const colorLocation = gl.getAttribLocation(program, 'a_color');

const stride = 5 * Float32Array.BYTES_PER_ELEMENT;

gl.bindBuffer(gl.ARRAY_BUFFER, vertexBuffer);

gl.enableVertexAttribArray(positionLocation);
gl.vertexAttribPointer(
  positionLocation,
  2,
  gl.FLOAT,
  false,
  stride,
  0,
);

gl.enableVertexAttribArray(colorLocation);
gl.vertexAttribPointer(
  colorLocation,
  3,
  gl.FLOAT,
  false,
  stride,
  2 * Float32Array.BYTES_PER_ELEMENT,
);
```

`vertexAttribPointer` is one of the most important calls in WebGL. It says how to decode bytes in the currently bound `ARRAY_BUFFER` into shader attributes.

Arguments:

| Argument | Meaning |
|---|---|
| location | Attribute location in shader program |
| size | Components per vertex, such as 2 for `vec2` |
| type | Data type, such as `FLOAT` |
| normalized | Convert integer data to normalized floats |
| stride | Bytes from one vertex record to the next |
| offset | Bytes to first component in the record |

### Draw

```javascript
function resizeCanvasToDisplaySize(canvas) {
  const width = canvas.clientWidth || canvas.width;
  const height = canvas.clientHeight || canvas.height;

  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
}

resizeCanvasToDisplaySize(canvas);
gl.viewport(0, 0, canvas.width, canvas.height);

gl.clearColor(0.05, 0.07, 0.09, 1.0);
gl.clear(gl.COLOR_BUFFER_BIT);

gl.useProgram(program);
gl.bindBuffer(gl.ARRAY_BUFFER, vertexBuffer);
gl.drawArrays(gl.TRIANGLES, 0, 3);
```

If you see a triangle, you have exercised the core pipeline:

- JavaScript data to GPU buffer,
- buffer layout to attributes,
- vertex shader,
- interpolation,
- fragment shader,
- framebuffer write.

### The Same Shape in OpenGL

Native OpenGL code has different setup details, but the shape is the same:

```c
glUseProgram(program);
glBindBuffer(GL_ARRAY_BUFFER, vertexBuffer);
glEnableVertexAttribArray(positionLocation);
glVertexAttribPointer(positionLocation, 2, GL_FLOAT, GL_FALSE, stride, 0);
glDrawArrays(GL_TRIANGLES, 0, 3);
```

This is why WebGL is such a good classroom for GL.

---

## Part 7 - Buffers, Attributes, Uniforms, and VAOs

Buffers move bulk data to the GPU. Attributes explain vertex layout. Uniforms configure a draw. Vertex array objects save vertex input state.

### Buffer Objects

Create and upload:

```javascript
const buffer = gl.createBuffer();
gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
```

Update part of a buffer:

```javascript
gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
gl.bufferSubData(gl.ARRAY_BUFFER, 0, updatedData);
```

Common buffer targets:

| Target | Role |
|---|---|
| `ARRAY_BUFFER` | Vertex data |
| `ELEMENT_ARRAY_BUFFER` | Indices |
| `COPY_READ_BUFFER` | WebGL 2 copy source |
| `COPY_WRITE_BUFFER` | WebGL 2 copy destination |
| `UNIFORM_BUFFER` | WebGL 2 uniform block data |
| `TRANSFORM_FEEDBACK_BUFFER` | WebGL 2 captured vertex shader output |

### Usage Hints

Buffer usage hints:

| Hint | Typical meaning |
|---|---|
| `STATIC_DRAW` | Upload rarely, draw often |
| `DYNAMIC_DRAW` | Update repeatedly, draw often |
| `STREAM_DRAW` | Use briefly, replace often |

They are hints to the implementation, not access permissions.

### Interleaved vs Separate Buffers

Interleaved:

```text
position color uv | position color uv | position color uv
```

Separate:

```text
positions...
colors...
uvs...
```

Interleaving often improves locality when attributes are used together. Separate buffers can be useful when some attributes update at different rates or are optional for different shaders.

### Index Buffers

Index buffers let vertices be reused.

```javascript
const indices = new Uint16Array([
  0, 1, 2,
  2, 1, 3,
]);

const indexBuffer = gl.createBuffer();
gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, indexBuffer);
gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, indices, gl.STATIC_DRAW);

gl.drawElements(gl.TRIANGLES, indices.length, gl.UNSIGNED_SHORT, 0);
```

Use `Uint16Array` for most meshes under 65,536 vertices. Use `Uint32Array` with WebGL 2 or the `OES_element_index_uint` extension in WebGL 1.

### Attribute Locations

You can query locations after linking:

```javascript
const positionLocation = gl.getAttribLocation(program, 'a_position');
```

Or bind them before linking:

```javascript
gl.bindAttribLocation(program, 0, 'a_position');
gl.linkProgram(program);
```

Stable explicit locations make renderers easier to reason about, especially in native OpenGL and WebGL 2 style code.

### Uniforms

Uniforms are per-program state.

```javascript
gl.useProgram(program);
gl.uniform1f(timeLocation, performance.now() / 1000);
gl.uniform2f(resolutionLocation, canvas.width, canvas.height);
gl.uniformMatrix4fv(matrixLocation, false, matrix);
```

Uniform values belong to the linked program object. If you switch programs, you need to set uniforms for that program.

### Uniform Buffer Objects

WebGL 2 adds uniform buffer objects. UBOs let you store uniform blocks in buffers and bind them for multiple programs.

GLSL:

```glsl
#version 300 es
layout(std140) uniform Scene {
  mat4 u_viewProjection;
  vec4 u_lightDirection;
};
```

JavaScript:

```javascript
const blockIndex = gl.getUniformBlockIndex(program, 'Scene');
gl.uniformBlockBinding(program, blockIndex, 0);
gl.bindBufferBase(gl.UNIFORM_BUFFER, 0, sceneBuffer);
```

The difficult part is `std140` layout. Padding matters. For example, `vec3` occupies 16 bytes in many uniform block layouts. Treat UBO layout as a binary ABI.

### Vertex Array Objects

Vertex array objects store vertex attribute setup. WebGL 2 has VAOs in core.

```javascript
const vao = gl.createVertexArray();
gl.bindVertexArray(vao);

gl.bindBuffer(gl.ARRAY_BUFFER, vertexBuffer);
gl.enableVertexAttribArray(positionLocation);
gl.vertexAttribPointer(positionLocation, 3, gl.FLOAT, false, stride, 0);

gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, indexBuffer);

gl.bindVertexArray(null);
```

Later:

```javascript
gl.bindVertexArray(vao);
gl.drawElements(gl.TRIANGLES, indexCount, gl.UNSIGNED_SHORT, 0);
```

Important detail: the `ELEMENT_ARRAY_BUFFER` binding is stored in the VAO. The `ARRAY_BUFFER` binding itself is not stored, but each attribute pointer records the buffer that was bound when `vertexAttribPointer` was called.

### Instancing

Instancing draws many copies of geometry with per-instance data.

```javascript
gl.vertexAttribDivisor(instanceOffsetLocation, 1);
gl.drawArraysInstanced(gl.TRIANGLES, 0, vertexCount, instanceCount);
```

An attribute divisor of `1` means advance this attribute once per instance instead of once per vertex.

Use instancing for:

- sprites,
- particles,
- repeated props,
- map markers,
- thousands of simple meshes.

---

## Part 8 - Matrices, Coordinates, and Cameras

GL does not have a camera. A camera is math you provide.

### Coordinate Spaces

Most renderers use a chain of coordinate spaces:

```text
local/object space
  -> world space
  -> view/camera space
  -> clip space
  -> normalized device coordinates
  -> screen pixels
```

Typical matrices:

| Matrix | Job |
|---|---|
| Model | Object to world |
| View | World to camera |
| Projection | Camera to clip |
| MVP | Projection * View * Model |

Vertex shader:

```glsl
attribute vec3 a_position;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

void main() {
  gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
```

Matrix order matters. GLSL matrices are column-major by convention, and vector multiplication is usually written with the matrix on the left.

### Clip Space

After multiplying by projection, the vertex is in clip space. The GPU clips primitives against the clip volume, then divides by `w`.

Perspective projection works because farther points tend to have larger `w`, and the divide shrinks `x` and `y`.

### Orthographic Projection

Orthographic projection keeps parallel lines parallel. It is useful for:

- 2D rendering,
- UI overlays,
- CAD views,
- tile maps,
- debug visualization.

Conceptually:

```javascript
function ortho(left, right, bottom, top, near, far) {
  return [
    2 / (right - left), 0, 0, 0,
    0, 2 / (top - bottom), 0, 0,
    0, 0, -2 / (far - near), 0,
    -(right + left) / (right - left),
    -(top + bottom) / (top - bottom),
    -(far + near) / (far - near),
    1,
  ];
}
```

### Perspective Projection

Perspective projection makes distant objects appear smaller.

Inputs:

- vertical field of view,
- aspect ratio,
- near plane,
- far plane.

The near and far planes strongly affect depth precision. A near plane of `0.001` and far plane of `100000` will create z-fighting. Push the near plane out as far as your scene allows.

### View Matrix

A view matrix is the inverse of the camera transform. If the camera moves right, the world appears to move left.

Common look-at inputs:

- eye position,
- target position,
- up direction.

```javascript
const view = lookAt(
  [3, 2, 5],
  [0, 0, 0],
  [0, 1, 0],
);
```

In production, use a tested math library such as `gl-matrix` unless you are specifically learning the math.

### Screen Coordinates

The viewport maps normalized device coordinates to pixels.

```javascript
gl.viewport(0, 0, canvas.width, canvas.height);
```

Canvas CSS size and drawing buffer size are different:

```javascript
const dpr = window.devicePixelRatio || 1;
canvas.width = Math.round(canvas.clientWidth * dpr);
canvas.height = Math.round(canvas.clientHeight * dpr);
gl.viewport(0, 0, canvas.width, canvas.height);
```

If your rendering looks blurry, check drawing buffer size.

### Y Axis Confusion

Different systems use different origins:

- Web canvas pixels often feel top-left oriented.
- GL clip space has positive Y upward.
- Texture coordinates usually put `(0, 0)` at the lower-left in GL tradition.
- Images loaded from the web often arrive in top-left row order.

WebGL provides:

```javascript
gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
```

This flips source image data during texture upload. Use it intentionally, not as a random fix.

---

## Part 9 - Textures, Samplers, and Pixel Data

Textures are GPU images. Shaders sample them.

### Create a Texture

```javascript
const texture = gl.createTexture();
gl.bindTexture(gl.TEXTURE_2D, texture);

gl.texImage2D(
  gl.TEXTURE_2D,
  0,
  gl.RGBA,
  1,
  1,
  0,
  gl.RGBA,
  gl.UNSIGNED_BYTE,
  new Uint8Array([255, 0, 255, 255]),
);
```

A 1x1 placeholder lets you render immediately while an image loads.

### Upload an Image

```javascript
const image = new Image();
image.crossOrigin = 'anonymous';
image.src = '/texture.png';
image.onload = () => {
  gl.bindTexture(gl.TEXTURE_2D, texture);
  gl.texImage2D(
    gl.TEXTURE_2D,
    0,
    gl.RGBA,
    gl.RGBA,
    gl.UNSIGNED_BYTE,
    image,
  );
  gl.generateMipmap(gl.TEXTURE_2D);
};
```

Cross-origin images require correct CORS headers if you want to sample them in WebGL.

### Texture Parameters

Texture parameters control sampling and wrapping:

```javascript
gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.REPEAT);
```

Common filters:

| Filter | Meaning |
|---|---|
| `NEAREST` | Pixelated nearest sample |
| `LINEAR` | Bilinear interpolation |
| `NEAREST_MIPMAP_NEAREST` | Nearest mip level, nearest texel |
| `LINEAR_MIPMAP_LINEAR` | Trilinear filtering |

Common wraps:

| Wrap | Meaning |
|---|---|
| `CLAMP_TO_EDGE` | Clamp UV to edge |
| `REPEAT` | Repeat texture |
| `MIRRORED_REPEAT` | Repeat with mirrored tiles |

### Power-of-Two Rules

WebGL 1 has restrictions for non-power-of-two textures. If a texture is not power-of-two in both dimensions, WebGL 1 requires:

- no mipmaps,
- `CLAMP_TO_EDGE` wrapping,
- compatible minification filter such as `LINEAR` or `NEAREST`.

Power-of-two dimensions are like 256, 512, 1024. WebGL 2 relaxes many of these restrictions.

### Texture Units

Shaders refer to sampler uniforms. Samplers point to texture units.

```javascript
gl.activeTexture(gl.TEXTURE0);
gl.bindTexture(gl.TEXTURE_2D, diffuseTexture);
gl.uniform1i(diffuseLocation, 0);

gl.activeTexture(gl.TEXTURE1);
gl.bindTexture(gl.TEXTURE_2D, normalTexture);
gl.uniform1i(normalLocation, 1);
```

This indirection is classic GL:

```text
sampler uniform -> texture unit -> texture object
```

### Mipmaps

Mipmaps are smaller versions of a texture. They improve quality and performance when textures shrink on screen.

```javascript
gl.generateMipmap(gl.TEXTURE_2D);
```

Without mipmaps, distant textured surfaces can shimmer because many source texels compete for one output pixel.

### Texture Formats

WebGL texture formats are a source of constant detail work.

Common WebGL 1 formats:

| Format | Use |
|---|---|
| `RGBA` + `UNSIGNED_BYTE` | Standard color texture |
| `RGB` + `UNSIGNED_BYTE` | Color without alpha |
| `ALPHA` | Single channel alpha in WebGL 1 |
| `LUMINANCE` | Legacy single channel |
| `LUMINANCE_ALPHA` | Legacy two channel |

WebGL 2 adds sized internal formats such as `RGBA8`, `R8`, `RG8`, `RGBA16F`, and integer formats.

### Floating-Point Textures

Floating-point textures are useful for HDR, simulation, height maps, GPGPU-style tricks, and post-processing.

In WebGL 1 they require extensions:

```javascript
const floatTextures = gl.getExtension('OES_texture_float');
const halfFloatTextures = gl.getExtension('OES_texture_half_float');
```

Rendering to floating-point textures requires additional extension support. Always check before relying on it.

---

## Part 10 - Framebuffers, Render Targets, and Post-Processing

The default framebuffer is the canvas. Custom framebuffers let you render somewhere else.

### Why Render Offscreen

Render-to-texture enables:

- post-processing effects,
- shadow maps,
- reflections,
- picking by object ID,
- deferred rendering,
- bloom,
- simulation feedback,
- screenshots or thumbnails.

### Create a Color Render Target

```javascript
const targetTexture = gl.createTexture();
gl.bindTexture(gl.TEXTURE_2D, targetTexture);
gl.texImage2D(
  gl.TEXTURE_2D,
  0,
  gl.RGBA,
  width,
  height,
  0,
  gl.RGBA,
  gl.UNSIGNED_BYTE,
  null,
);
gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);

const framebuffer = gl.createFramebuffer();
gl.bindFramebuffer(gl.FRAMEBUFFER, framebuffer);
gl.framebufferTexture2D(
  gl.FRAMEBUFFER,
  gl.COLOR_ATTACHMENT0,
  gl.TEXTURE_2D,
  targetTexture,
  0,
);
```

### Add Depth Storage

```javascript
const depthBuffer = gl.createRenderbuffer();
gl.bindRenderbuffer(gl.RENDERBUFFER, depthBuffer);
gl.renderbufferStorage(gl.RENDERBUFFER, gl.DEPTH_COMPONENT16, width, height);
gl.framebufferRenderbuffer(
  gl.FRAMEBUFFER,
  gl.DEPTH_ATTACHMENT,
  gl.RENDERBUFFER,
  depthBuffer,
);
```

### Check Completeness

```javascript
if (gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== gl.FRAMEBUFFER_COMPLETE) {
  throw new Error('Framebuffer is incomplete.');
}
```

Framebuffer completeness rules are strict. Attachments must have compatible sizes and formats.

### Render Pass Shape

WebGL does not have render pass objects, but you still structure rendering into passes:

```javascript
// First pass: scene to texture.
gl.bindFramebuffer(gl.FRAMEBUFFER, sceneFramebuffer);
gl.viewport(0, 0, width, height);
gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
drawScene();

// Second pass: texture to canvas.
gl.bindFramebuffer(gl.FRAMEBUFFER, null);
gl.viewport(0, 0, canvas.width, canvas.height);
drawFullscreenQuad(sceneTexture);
```

WebGPU names render passes explicitly. In GL, you impose the structure yourself through framebuffer binding and draw order.

### Fullscreen Triangle

Many post-process effects draw one fullscreen triangle instead of a quad.

Vertex shader:

```glsl
attribute vec2 a_position;
varying vec2 v_uv;

void main() {
  v_uv = a_position * 0.5 + 0.5;
  gl_Position = vec4(a_position, 0.0, 1.0);
}
```

Positions:

```javascript
new Float32Array([
  -1, -1,
   3, -1,
  -1,  3,
]);
```

The oversized triangle covers the screen without a diagonal seam.

### Multiple Render Targets

WebGL 2 supports multiple render targets:

```javascript
gl.drawBuffers([
  gl.COLOR_ATTACHMENT0,
  gl.COLOR_ATTACHMENT1,
]);
```

Fragment shader:

```glsl
#version 300 es
precision highp float;

layout(location = 0) out vec4 outColor;
layout(location = 1) out vec4 outNormal;

void main() {
  outColor = vec4(1.0);
  outNormal = vec4(0.0, 0.0, 1.0, 1.0);
}
```

MRT is the foundation of deferred rendering and many advanced pipelines.

---

## Part 11 - Depth, Stencil, Blending, and Transparency

The fragment shader does not automatically win. Fixed-function per-fragment operations decide whether and how the result reaches the framebuffer.

### Depth Testing

Depth testing keeps nearer fragments over farther fragments.

```javascript
gl.enable(gl.DEPTH_TEST);
gl.depthFunc(gl.LESS);
gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
```

Common depth functions:

| Function | Passes when |
|---|---|
| `LESS` | Incoming depth is smaller |
| `LEQUAL` | Incoming depth is smaller or equal |
| `GREATER` | Incoming depth is larger |
| `ALWAYS` | Always passes |

Depth buffers are finite precision. Most precision is near the camera in a perspective projection, so avoid extremely tiny near planes.

### Depth Writes

Depth testing and depth writing are separate:

```javascript
gl.depthMask(false); // stop writing depth
drawTransparentObjects();
gl.depthMask(true);
```

Transparent objects often test against depth but do not write depth.

### Face Culling

Face culling skips triangles facing away from the camera.

```javascript
gl.enable(gl.CULL_FACE);
gl.cullFace(gl.BACK);
gl.frontFace(gl.CCW);
```

By default, counter-clockwise triangles are front-facing. If your model disappears, winding order or a negative scale may be the cause.

### Blending

Blending combines source fragment color with destination framebuffer color.

Standard alpha blending:

```javascript
gl.enable(gl.BLEND);
gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
```

Equation:

```text
out = src * srcAlpha + dst * (1 - srcAlpha)
```

Additive blending:

```javascript
gl.blendFunc(gl.ONE, gl.ONE);
```

Useful for particles, glows, fire, and light accumulation.

### Premultiplied Alpha

With premultiplied alpha, RGB is already multiplied by alpha.

```javascript
gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
```

Browsers and images often involve premultiplied alpha. Be deliberate about it:

```javascript
gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
```

Mismatched alpha conventions create dark or bright halos around sprites.

### Transparency Sorting

Correct alpha blending usually requires drawing transparent objects back-to-front after opaque objects.

Common order:

1. Draw opaque objects with depth test and depth writes.
2. Sort transparent objects from far to near.
3. Draw transparent objects with depth test, blending, and depth writes disabled.

This is imperfect for intersecting transparent geometry. Advanced solutions include weighted blended order-independent transparency, depth peeling, or avoiding problematic transparency.

### Stencil Buffer

The stencil buffer stores small integer values per pixel. It is useful for:

- masks,
- mirrors,
- outlines,
- portals,
- UI clipping,
- constructive effects.

Example shape:

```javascript
gl.enable(gl.STENCIL_TEST);
gl.stencilFunc(gl.ALWAYS, 1, 0xff);
gl.stencilOp(gl.KEEP, gl.KEEP, gl.REPLACE);
drawMask();

gl.stencilFunc(gl.EQUAL, 1, 0xff);
gl.stencilOp(gl.KEEP, gl.KEEP, gl.KEEP);
drawOnlyInsideMask();
```

Stencil is powerful but state-heavy. Encapsulate it carefully.

---

## Part 12 - Performance, Debugging, and Production Practices

Fast WebGL is mostly about reducing CPU driver overhead, moving data predictably, and avoiding expensive GPU work per pixel.

### The Performance Thesis

The CPU prepares work. The driver validates and translates work. The GPU executes work. Bottlenecks can occur at any of those points.

Fast WebGL code usually:

- creates resources outside the frame loop,
- batches draw calls,
- minimizes state changes,
- avoids synchronous readbacks,
- keeps shaders simple enough for target devices,
- uses appropriate texture formats and mipmaps,
- uploads only changed data,
- measures on real devices.

### Avoid Per-Frame Resource Creation

Bad:

```javascript
function render() {
  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, frameData, gl.DYNAMIC_DRAW);
  gl.drawArrays(gl.TRIANGLES, 0, count);
}
```

Better:

```javascript
const buffer = gl.createBuffer();

function render() {
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferSubData(gl.ARRAY_BUFFER, 0, frameData);
  gl.drawArrays(gl.TRIANGLES, 0, count);
}
```

Create programs, buffers, textures, VAOs, and framebuffers during loading or resize, not during every frame.

### Batch Draw Calls

Each draw call has CPU overhead. Batching means drawing more work per call.

Techniques:

- combine static meshes,
- use texture atlases,
- sort by material,
- use instancing,
- use uniform buffers in WebGL 2,
- reduce program switches,
- reduce framebuffer switches.

Do not chase one giant draw call at all costs. The real goal is fewer expensive state changes and enough work per call.

### Avoid Readbacks

Calls that read GPU results can stall:

```javascript
gl.readPixels(...);
gl.getParameter(...);
gl.getError();
```

`gl.getError()` is useful for debugging, but do not scatter it through hot production paths. For picking, prefer rendering a small ID buffer only when needed, or use CPU-side spatial structures when appropriate.

### Texture Performance

Good texture hygiene:

- generate mipmaps for minified textures,
- use compressed textures when distribution pipeline allows,
- keep texture sizes reasonable,
- avoid frequent full texture uploads,
- use atlases for many sprites,
- avoid sampling too many large textures per fragment.

Compressed texture support is extension-based:

```javascript
const astc = gl.getExtension('WEBGL_compressed_texture_astc');
const s3tc = gl.getExtension('WEBGL_compressed_texture_s3tc');
const etc = gl.getExtension('WEBGL_compressed_texture_etc');
```

Production engines often ship multiple compressed texture formats and select at runtime.

### Shader Performance

Fragment shaders often dominate because they run per covered pixel. A fullscreen pass at high DPI can execute millions of fragment shader invocations.

Watch for:

- many dependent texture reads,
- dynamic loops,
- divergent branches,
- high precision where medium precision is enough,
- expensive math in fragment shaders,
- overdraw from particles or transparency.

Move work to the vertex shader when interpolation is acceptable. Precompute on the CPU when values change rarely.

### Context Loss

WebGL contexts can be lost. Treat it as a real production event.

```javascript
canvas.addEventListener('webglcontextlost', (event) => {
  event.preventDefault();
  stopRendering();
});

canvas.addEventListener('webglcontextrestored', () => {
  recreateAllGpuResources();
  startRendering();
});
```

When context is restored, GPU objects are gone. You must recreate buffers, textures, programs, framebuffers, and VAOs.

### Error Checking

Basic error helper:

```javascript
function checkGl(gl, label) {
  const error = gl.getError();
  if (error !== gl.NO_ERROR) {
    throw new Error(`${label}: WebGL error 0x${error.toString(16)}`);
  }
}
```

Use it around setup and suspicious paths, not every draw in a hot loop.

### Debug Extensions and Tools

Useful tools:

- browser devtools canvas inspection where available,
- `WEBGL_debug_renderer_info` for diagnostics,
- `KHR_debug` in WebGL 2 where available,
- Spector.js for frame capture,
- shader compile logs,
- reduced test scenes.

`WEBGL_debug_renderer_info` may be restricted for privacy. Do not rely on it for core behavior.

### Production Checklist

Before shipping:

- Feature-detect WebGL 2 and required extensions.
- Provide a fallback message or non-GL path.
- Handle context loss and restoration.
- Resize canvas using device pixel ratio intentionally.
- Compile and link shaders with useful logs.
- Check framebuffer completeness.
- Avoid per-frame resource creation.
- Avoid synchronous readback in animation loops.
- Test integrated GPUs and mobile devices.
- Test high-DPI displays.
- Test CORS behavior for textures.
- Budget GPU memory.

---

## Part 13 - Ecosystem, OpenGL Mapping, and Recipes

Most production WebGL is written through libraries, but raw WebGL remains worth learning.

### Libraries and Engines

| Tool | Role |
|---|---|
| Three.js | Popular 3D library with scene graph, materials, loaders |
| Babylon.js | Full-featured web 3D engine |
| PlayCanvas | Web-first game and 3D engine |
| PixiJS | Fast 2D renderer built around WebGL/WebGPU backends |
| regl | Functional WebGL command abstraction |
| twgl.js | Lightweight helpers from WebGL Fundamentals |
| luma.gl | Data visualization oriented GL abstraction |
| deck.gl | Large-scale data visualization |
| CesiumJS | Globe and geospatial visualization |
| Spector.js | WebGL frame debugger |

Use raw WebGL when:

- you are learning the graphics pipeline,
- you need a tiny custom renderer,
- you are debugging engine behavior,
- you need control a library hides,
- you are porting GL/OpenGL ES concepts.

Use a library when:

- you need model loading,
- you need cameras and controls,
- you need PBR materials,
- you need animation systems,
- you need production asset workflows,
- you are building an application rather than a renderer.

### WebGL to OpenGL Mapping

Many WebGL calls map directly to OpenGL ES or OpenGL:

| WebGL | OpenGL / GLES idea |
|---|---|
| `canvas.getContext('webgl')` | Create GL context through platform windowing API |
| `gl.createBuffer()` | `glGenBuffers` |
| `gl.bindBuffer()` | `glBindBuffer` |
| `gl.bufferData()` | `glBufferData` |
| `gl.createShader()` | `glCreateShader` |
| `gl.shaderSource()` | `glShaderSource` |
| `gl.compileShader()` | `glCompileShader` |
| `gl.createProgram()` | `glCreateProgram` |
| `gl.linkProgram()` | `glLinkProgram` |
| `gl.useProgram()` | `glUseProgram` |
| `gl.vertexAttribPointer()` | `glVertexAttribPointer` |
| `gl.drawArrays()` | `glDrawArrays` |
| `gl.drawElements()` | `glDrawElements` |
| `gl.createTexture()` | `glGenTextures` |
| `gl.texImage2D()` | `glTexImage2D` |
| `gl.createFramebuffer()` | `glGenFramebuffers` |

The biggest difference is context creation. Native OpenGL requires platform glue such as GLFW, SDL, EGL, WGL, GLX, CGL, or an engine. WebGL gets the context from a canvas.

### Recipe: Resize Correctly

```javascript
function resizeCanvasToDisplaySize(canvas, multiplier = window.devicePixelRatio || 1) {
  const width = Math.floor(canvas.clientWidth * multiplier);
  const height = Math.floor(canvas.clientHeight * multiplier);

  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
    return true;
  }

  return false;
}

function render() {
  resizeCanvasToDisplaySize(gl.canvas);
  gl.viewport(0, 0, gl.canvas.width, gl.canvas.height);
  draw();
  requestAnimationFrame(render);
}
```

### Recipe: A Small Program Helper

```javascript
function createProgramFromSources(gl, vertexSource, fragmentSource) {
  const program = createProgram(gl, vertexSource, fragmentSource);

  return {
    program,
    attrib(name) {
      const location = gl.getAttribLocation(program, name);
      if (location < 0) {
        throw new Error(`Missing attribute: ${name}`);
      }
      return location;
    },
    uniform(name) {
      const location = gl.getUniformLocation(program, name);
      if (!location) {
        throw new Error(`Missing uniform: ${name}`);
      }
      return location;
    },
  };
}
```

Note that a uniform can be optimized out if the shader does not use it. In that case `getUniformLocation` returns `null`.

### Recipe: Texture Atlas Sprites

Store many sprites in one texture and use UV rectangles.

Vertex data per sprite:

```text
x, y, u, v
```

Benefits:

- fewer texture binds,
- larger batches,
- simpler sprite renderer.

Costs:

- atlas packing,
- bleeding between sprites unless padding is handled,
- maximum texture size limits.

### Recipe: Picking With an ID Buffer

Render object IDs into an offscreen framebuffer, then read one pixel under the pointer.

Fragment shader:

```glsl
precision mediump float;
uniform vec4 u_idColor;

void main() {
  gl_FragColor = u_idColor;
}
```

Read:

```javascript
const pixel = new Uint8Array(4);
gl.bindFramebuffer(gl.FRAMEBUFFER, pickingFramebuffer);
gl.readPixels(x, y, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
```

Remember that readback can stall. Do this only on interaction, not every frame without need.

### Recipe: Particle Instancing

Use one quad mesh and per-instance attributes:

- instance position,
- instance scale,
- instance color,
- instance rotation.

Draw:

```javascript
gl.bindVertexArray(particleVao);
gl.drawArraysInstanced(gl.TRIANGLES, 0, 6, particleCount);
```

This turns thousands of sprite draw calls into one draw call.

### Recipe: Post-Processing Pipeline

Common shape:

1. Render scene into HDR or normal color texture.
2. Render bright areas into bloom texture.
3. Blur bloom texture with ping-pong framebuffers.
4. Composite scene and bloom to canvas.
5. Apply tone mapping and gamma correction.

Even in WebGL, think in passes. Framebuffer binding is your pass boundary.

### Learning Path

1. Draw a triangle.
2. Draw indexed geometry.
3. Add a matrix uniform and move the triangle.
4. Render textured quads.
5. Build a 2D sprite batcher.
6. Add a perspective camera and draw cubes.
7. Add depth testing and face culling.
8. Render to a texture and do a grayscale post-process.
9. Add instanced particles.
10. Capture a frame in Spector.js and explain every draw call.

### The Final Mental Model

In GL, think:

```text
Which program is current?
Which buffers are bound?
How are attributes decoded?
Which uniforms and textures does this program see?
Which framebuffer receives the result?
Which fixed-function tests and blend modes are active?
What draw call consumes all of that state?
```

That is the whole game. WebGL teaches this model with browser ergonomics, but the concepts are OpenGL concepts. Once you can reason about state, data layout, shader stages, and framebuffer output, most real-time graphics APIs become less mysterious.
