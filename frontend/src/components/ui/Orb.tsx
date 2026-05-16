"use client";
import { useEffect, useRef } from "react";

/**
 * Animated WebGL orb. Multiple visual variants — pick via `variant` prop.
 *   • swirl   — original DAIC purple/teal/violet simplex-noise swirl
 *   • aurora  — multi-band flowing wave (purple + teal + pink)
 *   • nebula  — soft cosmic cloud with fBm noise (purple → blue → pink)
 *   • halo    — minimal pulsing ring (purple ↔ teal shift)
 */
export type OrbVariant = "swirl" | "aurora" | "nebula" | "halo";

interface OrbProps {
  variant?: OrbVariant;
  active?: boolean;
  hue?: number;            // only used by swirl
  hoverIntensity?: number; // only used by swirl
  className?: string;
}

const VERT = `
precision highp float;
attribute vec2 position;
attribute vec2 uv;
varying vec2 vUv;
void main(){ vUv=uv; gl_Position=vec4(position,0.0,1.0); }`;

const FRAG_SWIRL = `
precision highp float;
uniform float iTime;
uniform vec3  iResolution;
uniform float hue;
uniform float hover;
uniform float rot;
uniform float hoverIntensity;
uniform vec3  backgroundColor;
varying vec2  vUv;

vec3 rgb2yiq(vec3 c){float y=dot(c,vec3(.299,.587,.114));float i=dot(c,vec3(.596,-.274,-.322));float q=dot(c,vec3(.211,-.523,.312));return vec3(y,i,q);}
vec3 yiq2rgb(vec3 c){return vec3(c.x+.956*c.y+.621*c.z,c.x-.272*c.y-.647*c.z,c.x-1.106*c.y+1.703*c.z);}
vec3 adjustHue(vec3 color,float hueDeg){float h=hueDeg*3.14159265/180.0;vec3 yiq=rgb2yiq(color);float cosA=cos(h);float sinA=sin(h);float i2=yiq.y*cosA-yiq.z*sinA;float q2=yiq.y*sinA+yiq.z*cosA;yiq.y=i2;yiq.z=q2;return yiq2rgb(yiq);}
vec3 hash33(vec3 p3){p3=fract(p3*vec3(.1031,.11369,.13787));p3+=dot(p3,p3.yxz+19.19);return -1.0+2.0*fract(vec3(p3.x+p3.y,p3.x+p3.z,p3.y+p3.z)*p3.zyx);}
float snoise3(vec3 p){const float K1=.333333333;const float K2=.166666667;vec3 i=floor(p+(p.x+p.y+p.z)*K1);vec3 d0=p-(i-(i.x+i.y+i.z)*K2);vec3 e=step(vec3(0.0),d0-d0.yzx);vec3 i1=e*(1.0-e.zxy);vec3 i2=1.0-e.zxy*(1.0-e);vec3 d1=d0-(i1-K2);vec3 d2=d0-(i2-K1);vec3 d3=d0-0.5;vec4 h=max(0.6-vec4(dot(d0,d0),dot(d1,d1),dot(d2,d2),dot(d3,d3)),0.0);vec4 n=h*h*h*h*vec4(dot(d0,hash33(i)),dot(d1,hash33(i+i1)),dot(d2,hash33(i+i2)),dot(d3,hash33(i+1.0)));return dot(vec4(31.316),n);}
vec4 extractAlpha(vec3 c){float a=max(max(c.r,c.g),c.b);return vec4(c/(a+1e-5),a);}
const vec3 baseColor1=vec3(.611765,.262745,.996078);
const vec3 baseColor2=vec3(.298039,.760784,.913725);
const vec3 baseColor3=vec3(.062745,.078431,.600000);
const float innerRadius=0.6;
const float noiseScale=0.65;
float light1(float i,float a,float d){return i/(1.0+d*a);}
float light2(float i,float a,float d){return i/(1.0+d*d*a);}
vec4 draw(vec2 uv){
  vec3 c1=adjustHue(baseColor1,hue);vec3 c2=adjustHue(baseColor2,hue);vec3 c3=adjustHue(baseColor3,hue);
  float ang=atan(uv.y,uv.x);float len=length(uv);float invLen=len>0.0?1.0/len:0.0;
  float bgLum=dot(backgroundColor,vec3(.299,.587,.114));
  float n0=snoise3(vec3(uv*noiseScale,iTime*0.5))*0.5+0.5;
  float r0=mix(mix(innerRadius,1.0,0.4),mix(innerRadius,1.0,0.6),n0);
  float d0=distance(uv,(r0*invLen)*uv);
  float v0=light1(1.0,10.0,d0);
  v0*=smoothstep(r0*1.05,r0,len);
  float innerFade=smoothstep(r0*0.8,r0*0.95,len);
  v0*=mix(innerFade,1.0,bgLum*0.7);
  float cl=cos(ang+iTime*2.0)*0.5+0.5;
  float a2=iTime*-1.0;vec2 pos=vec2(cos(a2),sin(a2))*r0;float d=distance(uv,pos);
  float v1=light2(1.5,5.0,d);v1*=light1(1.0,50.0,d0);
  float v2=smoothstep(1.0,mix(innerRadius,1.0,n0*0.5),len);
  float v3=smoothstep(innerRadius,mix(innerRadius,1.0,0.5),len);
  vec3 colBase=mix(c1,c2,cl);
  float fadeAmt=mix(1.0,0.1,bgLum);
  vec3 darkCol=mix(c3,colBase,v0);darkCol=(darkCol+v1)*v2*v3;darkCol=clamp(darkCol,0.0,1.0);
  vec3 lightCol=(colBase+v1)*mix(1.0,v2*v3,fadeAmt);lightCol=mix(backgroundColor,lightCol,v0);lightCol=clamp(lightCol,0.0,1.0);
  vec3 fc=mix(darkCol,lightCol,bgLum);
  return extractAlpha(fc);
}
vec4 mainImage(vec2 fragCoord){
  vec2 center=iResolution.xy*0.5;float sz=min(iResolution.x,iResolution.y);
  vec2 uv=(fragCoord-center)/sz*2.0;
  float s2=sin(rot);float c2=cos(rot);uv=vec2(c2*uv.x-s2*uv.y,s2*uv.x+c2*uv.y);
  uv.x+=hover*hoverIntensity*0.1*sin(uv.y*10.0+iTime);
  uv.y+=hover*hoverIntensity*0.1*sin(uv.x*10.0+iTime);
  return draw(uv);
}
void main(){
  vec2 fc=vUv*iResolution.xy;vec4 col=mainImage(fc);
  gl_FragColor=vec4(col.rgb*col.a,col.a);
}`;

// ── Aurora — flowing color bands ───────────────────────────────────────────────
const FRAG_AURORA = `
precision highp float;
uniform float iTime;
uniform vec3  iResolution;
uniform float hover;
varying vec2  vUv;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
  vec2 i = floor(p); vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i+vec2(1,0)), u.x),
             mix(hash(i+vec2(0,1)), hash(i+vec2(1,1)), u.x), u.y);
}
float fbm(vec2 p) {
  float v = 0.0; float a = 0.5;
  for (int i = 0; i < 4; i++) { v += a * noise(p); p *= 2.0; a *= 0.5; }
  return v;
}

void main() {
  vec2 center = iResolution.xy * 0.5;
  float sz   = min(iResolution.x, iResolution.y);
  vec2 uv    = (vUv * iResolution.xy - center) / sz * 2.0;
  float t    = iTime * (0.25 + hover * 0.35);
  float r    = length(uv);
  float mask = smoothstep(1.0, 0.0, r);

  float n1 = fbm(uv * 2.0 + vec2(t, t * 0.5));
  float n2 = fbm(uv * 3.0 + vec2(-t * 1.3, t * 0.7));
  float n3 = fbm(uv * 1.5 + vec2(t * 0.7, -t * 0.9));

  vec3 c1 = vec3(0.49, 0.42, 0.94);
  vec3 c2 = vec3(0.31, 0.80, 0.77);
  vec3 c3 = vec3(0.93, 0.42, 0.75);

  vec3 col = c1 * n1 + c2 * n2 + c3 * n3;
  col *= mask * (1.2 + hover * 0.4);

  float alpha = clamp(max(max(col.r, col.g), col.b), 0.0, 1.0);
  gl_FragColor = vec4(col * alpha, alpha);
}`;

// ── Nebula — soft cosmic cloud (fBm) ───────────────────────────────────────────
const FRAG_NEBULA = `
precision highp float;
uniform float iTime;
uniform vec3  iResolution;
uniform float hover;
varying vec2  vUv;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
  vec2 i = floor(p); vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i+vec2(1,0)), u.x),
             mix(hash(i+vec2(0,1)), hash(i+vec2(1,1)), u.x), u.y);
}
float fbm(vec2 p) {
  float v = 0.0; float a = 0.5;
  for (int i = 0; i < 5; i++) { v += a * noise(p); p *= 2.0; a *= 0.5; }
  return v;
}

void main() {
  vec2 center = iResolution.xy * 0.5;
  float sz   = min(iResolution.x, iResolution.y);
  vec2 uv    = (vUv * iResolution.xy - center) / sz * 2.0;
  float t    = iTime * (0.12 + hover * 0.15);
  float r    = length(uv);
  float falloff = exp(-r * 1.6) * 1.4;

  float n  = fbm(uv * 1.8 + vec2(t, t * 0.4));
  float n2 = fbm(uv * 4.0 - vec2(t * 0.3, t * 0.6));

  vec3 deep = vec3(0.50, 0.20, 0.95);
  vec3 mid  = vec3(0.30, 0.55, 0.95);
  vec3 edge = vec3(0.98, 0.50, 0.85);

  vec3 col = mix(deep, mid, n);
  col = mix(col, edge, smoothstep(0.35, 0.75, n));
  col += vec3(0.4, 0.4, 0.6) * n2 * 0.25;
  col *= falloff;

  float alpha = clamp(max(max(col.r, col.g), col.b), 0.0, 1.0);
  gl_FragColor = vec4(col * alpha, alpha);
}`;

// ── Halo — minimal pulsing ring ────────────────────────────────────────────────
const FRAG_HALO = `
precision highp float;
uniform float iTime;
uniform vec3  iResolution;
uniform float hover;
varying vec2  vUv;

void main() {
  vec2 center = iResolution.xy * 0.5;
  float sz   = min(iResolution.x, iResolution.y);
  vec2 uv    = (vUv * iResolution.xy - center) / sz * 2.0;
  float t    = iTime * (0.4 + hover * 0.6);
  float r    = length(uv);

  float radius = 0.55 + sin(t) * 0.025 + hover * 0.04;
  float ring   = exp(-pow(r - radius, 2.0) * 80.0);
  ring        += 0.5 * exp(-pow(r - radius, 2.0) * 14.0);
  float core   = exp(-r * 5.0) * 0.35;

  // Slow color shift
  float h = sin(t * 0.4) * 0.5 + 0.5;
  vec3 c1 = vec3(0.49, 0.42, 0.94);
  vec3 c2 = vec3(0.31, 0.80, 0.77);
  vec3 col = mix(c1, c2, h);

  col *= (ring + core) * (1.0 + hover * 0.4);
  float alpha = clamp(max(max(col.r, col.g), col.b), 0.0, 1.0);
  gl_FragColor = vec4(col * alpha, alpha);
}`;

const FRAG_MAP: Record<OrbVariant, string> = {
  swirl:  FRAG_SWIRL,
  aurora: FRAG_AURORA,
  nebula: FRAG_NEBULA,
  halo:   FRAG_HALO,
};

function compile(gl: WebGLRenderingContext, type: number, src: string) {
  const s = gl.createShader(type);
  if (!s) return null;
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
    console.error("Shader compile error:", gl.getShaderInfoLog(s));
    gl.deleteShader(s);
    return null;
  }
  return s;
}

export default function Orb({
  variant = "swirl",
  active  = false,
  hue     = 0,
  hoverIntensity = 0.2,
  className = "",
}: OrbProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const stateRef     = useRef({ targetHover: 0 });

  useEffect(() => { stateRef.current.targetHover = active ? 1 : 0; }, [active]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const canvas = document.createElement("canvas");
    canvas.style.width = "100%";
    canvas.style.height = "100%";
    container.appendChild(canvas);

    const gl = canvas.getContext("webgl", { alpha: true, premultipliedAlpha: false, antialias: false });
    if (!gl) { console.warn("WebGL not available"); return; }

    const vs = compile(gl, gl.VERTEX_SHADER, VERT);
    const fs = compile(gl, gl.FRAGMENT_SHADER, FRAG_MAP[variant]);
    if (!vs || !fs) return;

    const pgm = gl.createProgram();
    if (!pgm) return;
    gl.attachShader(pgm, vs);
    gl.attachShader(pgm, fs);
    gl.linkProgram(pgm);
    if (!gl.getProgramParameter(pgm, gl.LINK_STATUS)) {
      console.error("Program link error:", gl.getProgramInfoLog(pgm));
      return;
    }
    gl.useProgram(pgm);

    const posLoc = gl.getAttribLocation(pgm, "position");
    const uvLoc  = gl.getAttribLocation(pgm, "uv");

    const posBuf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, posBuf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 3,-1, -1,3]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(posLoc);
    gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 0, 0);

    const uvBuf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, uvBuf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([0,0, 2,0, 0,2]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(uvLoc);
    gl.vertexAttribPointer(uvLoc, 2, gl.FLOAT, false, 0, 0);

    // Some uniforms may not exist in every shader — getUniformLocation returns
    // null and gl.uniformXf(null, …) is a safe no-op.
    const u = {
      iTime:           gl.getUniformLocation(pgm, "iTime"),
      iResolution:     gl.getUniformLocation(pgm, "iResolution"),
      hue:             gl.getUniformLocation(pgm, "hue"),
      hover:           gl.getUniformLocation(pgm, "hover"),
      rot:             gl.getUniformLocation(pgm, "rot"),
      hoverIntensity:  gl.getUniformLocation(pgm, "hoverIntensity"),
      backgroundColor: gl.getUniformLocation(pgm, "backgroundColor"),
    };

    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.clearColor(0, 0, 0, 0);

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const w = container.clientWidth;
      const h = container.clientHeight;
      canvas.width  = w * dpr;
      canvas.height = h * dpr;
      gl.viewport(0, 0, canvas.width, canvas.height);
    };
    resize();
    window.addEventListener("resize", resize);

    let currentHover = 0;
    let currentRot   = 0;
    let lastTs       = 0;
    let raf          = 0;
    const bg = [0.02, 0.02, 0.06];

    const loop = (ts: number) => {
      raf = requestAnimationFrame(loop);
      const t  = ts * 0.001;
      const dt = lastTs ? t - lastTs : 0.016;
      lastTs = t;

      currentHover += (stateRef.current.targetHover - currentHover) * Math.min(dt * 4, 1);
      if (currentHover > 0.5) currentRot += dt * 0.3;

      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.uniform1f(u.iTime, t);
      gl.uniform3f(u.iResolution, canvas.width, canvas.height, canvas.width / canvas.height);
      gl.uniform1f(u.hue, hue);
      gl.uniform1f(u.hover, currentHover);
      gl.uniform1f(u.rot, currentRot);
      gl.uniform1f(u.hoverIntensity, hoverIntensity);
      gl.uniform3f(u.backgroundColor, bg[0], bg[1], bg[2]);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    };
    raf = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      if (canvas.parentNode) canvas.parentNode.removeChild(canvas);
      const ext = gl.getExtension("WEBGL_lose_context");
      if (ext) ext.loseContext();
    };
  }, [variant, hue, hoverIntensity]);

  return <div ref={containerRef} className={`pointer-events-none ${className}`} aria-hidden="true" />;
}
