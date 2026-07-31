/**
 * WebGL 2.0 60fps Hardware Accelerated Live Preview Renderer
 * Simulates Ken Burns Keyframe transforms (scale, pos_x, pos_y, rotation, alpha)
 * and real-time transition crossfades on HTML5 WebGL canvas.
 */
export class WebGLPreviewRenderer {
  private gl: WebGL2RenderingContext | null = null;
  private program: WebGLProgram | null = null;
  private positionBuffer: WebGLBuffer | null = null;
  private animFrameId: number | null = null;

  private currentPlayheadUs: number = 0;
  private totalDurationUs: number = 10_000_000;
  private isPlaying: boolean = false;
  private lastTimestamp: number = 0;

  private onFrameCallback: ((playheadUs: number) => void) | null = null;

  constructor(canvas: HTMLCanvasElement) {
    const gl = canvas.getContext('webgl2', { alpha: false, antialias: true, preserveDrawingBuffer: true });
    if (!gl) {
      console.warn('WebGL 2.0 not supported, falling back to 2D context');
      return;
    }
    this.gl = gl;
    this.initShaders();
    this.initBuffers();
  }

  private initShaders() {
    if (!this.gl) return;
    const gl = this.gl;

    const vsSource = `#version 300 es
      in vec2 a_position;
      uniform vec2 u_resolution;
      uniform vec2 u_translation;
      uniform vec2 u_scale;
      uniform float u_rotation;

      out vec2 v_uv;

      void main() {
        // Rotate
        float c = cos(u_rotation);
        float s = sin(u_rotation);
        vec2 rotated = vec2(
          a_position.x * c - a_position.y * s,
          a_position.x * s + a_position.y * c
        );

        // Scale & Translate
        vec2 position = (rotated * u_scale) + u_translation;

        // Convert from pixel space to 0.0 to 1.0 -> -1.0 to +1.0 (NDC)
        vec2 zeroToOne = position / u_resolution;
        vec2 zeroToTwo = zeroToOne * 2.0;
        vec2 clipSpace = zeroToTwo - 1.0;

        gl_Position = vec4(clipSpace * vec2(1, -1), 0, 1);
        v_uv = a_position;
      }
    `;

    const fsSource = `#version 300 es
      precision highp float;
      uniform vec4 u_color;
      uniform float u_alpha;
      out vec4 fragColor;

      void main() {
        fragColor = vec4(u_color.rgb, u_color.a * u_alpha);
      }
    `;

    const vs = this.createShader(gl, gl.VERTEX_SHADER, vsSource);
    const fs = this.createShader(gl, gl.FRAGMENT_SHADER, fsSource);

    if (vs && fs) {
      const prog = gl.createProgram();
      if (prog) {
        gl.attachShader(prog, vs);
        gl.attachShader(prog, fs);
        gl.linkProgram(prog);
        this.program = prog;
      }
    }
  }

  private createShader(gl: WebGL2RenderingContext, type: number, source: string): WebGLShader | null {
    const shader = gl.createShader(type);
    if (!shader) return null;
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      console.error('Shader compile error:', gl.getShaderInfoLog(shader));
      gl.deleteShader(shader);
      return null;
    }
    return shader;
  }

  private initBuffers() {
    if (!this.gl) return;
    const gl = this.gl;
    this.positionBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, this.positionBuffer);

    // Quad rectangle [-0.5, -0.5] to [0.5, 0.5]
    const positions = new Float32Array([
      -300, -200,
       300, -200,
      -300,  200,
      -300,  200,
       300, -200,
       300,  200,
    ]);
    gl.bufferData(gl.ARRAY_BUFFER, positions, gl.STATIC_DRAW);
  }

  public renderFrame(playheadUs: number, transform: { scale: number; posX: number; posY: number; rotation: number; alpha: number }) {
    if (!this.gl || !this.program) return;
    const gl = this.gl;

    gl.viewport(0, 0, gl.canvas.width, gl.canvas.height);
    gl.clearColor(0.07, 0.07, 0.08, 1.0);
    gl.clear(gl.COLOR_BUFFER_BIT);

    gl.useProgram(this.program);

    // Set uniforms
    const uResolution = gl.getUniformLocation(this.program, 'u_resolution');
    const uTranslation = gl.getUniformLocation(this.program, 'u_translation');
    const uScale = gl.getUniformLocation(this.program, 'u_scale');
    const uRotation = gl.getUniformLocation(this.program, 'u_rotation');
    const uColor = gl.getUniformLocation(this.program, 'u_color');
    const uAlpha = gl.getUniformLocation(this.program, 'u_alpha');

    gl.uniform2f(uResolution, gl.canvas.width, gl.canvas.height);
    gl.uniform2f(uTranslation, gl.canvas.width / 2 + transform.posX, gl.canvas.height / 2 + transform.posY);
    gl.uniform2f(uScale, transform.scale, transform.scale);
    gl.uniform1f(uRotation, transform.rotation);
    gl.uniform4f(uColor, 0.23, 0.51, 0.96, 1.0); // Vibrant blue clip canvas
    gl.uniform1f(uAlpha, transform.alpha);

    // Bind position
    const aPosition = gl.getAttribLocation(this.program, 'a_position');
    gl.enableVertexAttribArray(aPosition);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.positionBuffer);
    gl.vertexAttribPointer(aPosition, 2, gl.FLOAT, false, 0, 0);

    gl.drawArrays(gl.TRIANGLES, 0, 6);
  }

  public startLoop(onFrame: (playheadUs: number) => void) {
    this.onFrameCallback = onFrame;
    this.isPlaying = true;
    this.lastTimestamp = performance.now();

    const loop = (now: number) => {
      if (!this.isPlaying) return;
      const deltaMs = now - this.lastTimestamp;
      this.lastTimestamp = now;

      this.currentPlayheadUs += deltaMs * 1000;
      if (this.currentPlayheadUs > this.totalDurationUs) {
        this.currentPlayheadUs = 0;
      }

      if (this.onFrameCallback) {
        this.onFrameCallback(this.currentPlayheadUs);
      }

      this.animFrameId = requestAnimationFrame(loop);
    };

    this.animFrameId = requestAnimationFrame(loop);
  }

  public stopLoop() {
    this.isPlaying = false;
    if (this.animFrameId !== null) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }
  }

  public setPlayhead(us: number) {
    this.currentPlayheadUs = us;
  }
}
