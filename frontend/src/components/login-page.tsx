import { useEffect, useMemo, useRef, useState } from "react"
import type { SyntheticEvent } from "react"
import logo from "@/assets/c5i-logo.png"
import { signIn } from "@/lib/auth"
import type { AuthUser } from "@/lib/auth"
import "./login.css"

type Pt = [number, number]
interface Ribbon { a: Pt[]; b: Pt[]; n: number; grad: string; w: number; o: number; twist: number; glow?: boolean; glowMax?: number }
interface Strand { d: string; grad: string; width: number; opacity: number }

// 7 points per edge: P0 P1 P2 P3 | P4 P5 P6 (P4 is recomputed from P2/P3 for a smooth join).
const RIBBONS: Ribbon[] = [
  { a: [[-20, -10], [140, 30], [320, 250], [540, 470], [0, 0], [960, 620], [1180, 690]], b: [[-20, 318], [150, 290], [300, 390], [540, 520], [0, 0], [960, 780], [1180, 740]], n: 60, grad: "gPurple", w: .6, o: .5, twist: .10 },
  { a: [[-20, 314], [110, 304], [270, 385], [430, 495], [0, 0], [860, 590], [1120, 520]], b: [[-20, 330], [125, 334], [300, 430], [470, 545], [0, 0], [900, 630], [1120, 560]], n: 8, grad: "gCore", w: 1.3, o: 1, twist: .04, glow: true },
  { a: [[270, 385], [450, 330], [640, 430], [820, 440], [0, 0], [1000, 330], [1120, 230]], b: [[270, 395], [480, 440], [700, 520], [880, 530], [0, 0], [1020, 500], [1120, 480]], n: 56, grad: "gBlue", w: .55, o: .45, twist: .12 },
  { a: [[430, 480], [540, 560], [660, 610], [820, 590], [0, 0], [1000, 490], [1120, 480]], b: [[440, 520], [560, 630], [700, 700], [860, 690], [0, 0], [1030, 690], [1120, 700]], n: 46, grad: "gBlue", w: .6, o: .5, twist: .10, glow: true, glowMax: .18 },
  { a: [[-20, 630], [120, 680], [240, 735], [420, 790], [0, 0], [700, 860], [900, 880]], b: [[-20, 720], [140, 780], [290, 830], [470, 865], [0, 0], [720, 915], [900, 930]], n: 30, grad: "gPurple", w: .55, o: .3, twist: .08 },
  { a: [[1400, 380], [1500, 330], [1600, 280], [1700, 250], [0, 0], [1850, 200], [1900, 190]], b: [[1400, 520], [1500, 470], [1600, 400], [1700, 350], [0, 0], [1850, 290], [1900, 260]], n: 26, grad: "gPurple", w: .55, o: .35, twist: .08 },
  { a: [[1450, 760], [1560, 730], [1660, 700], [1760, 670], [0, 0], [1860, 630], [1900, 610]], b: [[1450, 830], [1560, 800], [1680, 760], [1780, 720], [0, 0], [1870, 690], [1900, 670]], n: 20, grad: "gPurple", w: .55, o: .3, twist: .06 },
]

const mix = (p: Pt, q: Pt, t: number): Pt => [p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t]
const fmt = (p: Pt) => p[0].toFixed(1) + " " + p[1].toFixed(1)

function pathFor(a: Pt[], b: Pt[], u: number, twist: number): string {
  const pts = a.map((_, k) => mix(a[k], b[k], Math.min(1, Math.max(0, u + twist * Math.sin(u * Math.PI * 2) * Math.sin(k * 1.3 + 1)))))
  pts[4] = [2 * pts[3][0] - pts[2][0], 2 * pts[3][1] - pts[2][1]]
  return `M${fmt(pts[0])} C${fmt(pts[1])} ${fmt(pts[2])} ${fmt(pts[3])} C${fmt(pts[4])} ${fmt(pts[5])} ${fmt(pts[6])}`
}

/** Hairlines blended between each ribbon's two edge curves, like silk threads. */
function buildStrands(): { mesh: Strand[]; glow: Strand[] } {
  // The four main ribbons run further right so they pass behind the card instead of stopping at an edge.
  const ribbons = RIBBONS.map((r, i): Ribbon => {
    if (i > 3) return r
    const stretch = (edge: Pt[]) => edge.map((p, k): Pt => k === 5 ? [900 + (p[0] - 900) * 1.7, p[1]] : k === 6 ? [900 + (p[0] - 900) * 2.8, p[1]] : p)
    return { ...r, a: stretch(r.a), b: stretch(r.b) }
  })
  const mesh: Strand[] = [], glow: Strand[] = []
  for (const r of ribbons) {
    for (let i = 0; i < r.n; i++) {
      const u = i / (r.n - 1)
      const d = pathFor(r.a, r.b, u, r.twist)
      const edge = 0.65 + 0.35 * Math.abs(Math.cos(u * Math.PI))
      mesh.push({ d, grad: r.grad, width: r.w * 1.25, opacity: Math.min(1, r.o * edge * 1.45) })
      if (r.glow && i % 2 === 0 && u <= (r.glowMax ?? 1)) glow.push({ d, grad: r.grad, width: 3.5 * 1.25, opacity: Math.min(1, .55 * 1.45) })
    }
  }
  return { mesh, glow }
}

const stops = (items: Array<[number, string, number]>) => items.map(([offset, color, opacity]) => <stop key={offset} offset={offset} stopColor={color} stopOpacity={opacity} />)

export function LoginPage({ onSignedIn }: { onSignedIn: (user: AuthUser) => void }) {
  const strands = useMemo(() => buildStrands(), [])
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [remember, setRemember] = useState(true)
  const [showPassword, setShowPassword] = useState(false)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState<{ text: string; kind: "" | "danger" | "success" }>({ text: "", kind: "" })
  const emailRef = useRef<HTMLInputElement>(null)
  useEffect(() => { const t = setTimeout(() => emailRef.current?.focus(), 200); return () => clearTimeout(t) }, [])

  async function submit(event: SyntheticEvent) {
    event.preventDefault()
    if (!email.trim() || !password) { setStatus({ text: "Please fill in all fields", kind: "danger" }); return }
    setBusy(true)
    setStatus({ text: "Signing in…", kind: "" })
    try {
      const user = await signIn(email.trim(), password, remember)
      setStatus({ text: "Login successful! Redirecting…", kind: "success" })
      onSignedIn(user)
    } catch (cause) {
      setStatus({ text: cause instanceof Error ? cause.message : "An error occurred. Please try again.", kind: "danger" })
      setBusy(false)
    }
  }

  return (
    <div className="lg-root"><main className="lg-page">
      <div className="lg-waves" aria-hidden="true">
        <svg viewBox="0 0 1810 869" preserveAspectRatio="xMidYMid slice">
          <defs>
            <linearGradient id="gPurple" x1="0" y1="0" x2="1" y2="0">{stops([[0, "#6a3dff", .15], [.3, "#9a5bff", .95], [.7, "#c79bff", .6], [1, "#6e43ff", 0]])}</linearGradient>
            <linearGradient id="gBlue" x1="0" y1="0" x2="1" y2="0">{stops([[0, "#7a4dff", .2], [.5, "#3b82ff", .9], [1, "#7d5cff", 0]])}</linearGradient>
            <linearGradient id="gCore" x1="0" y1="0" x2="1" y2="0">{stops([[0, "#8a5bff", .5], [.35, "#c9b0ff", 1], [.65, "#7fb0ff", 1], [1, "#6e5bff", .3]])}</linearGradient>
            <filter id="lgBlur" filterUnits="userSpaceOnUse" x="-200" y="-200" width="2400" height="1300"><feGaussianBlur stdDeviation="7" /></filter>
          </defs>
          <g filter="url(#lgBlur)">{strands.glow.map((s, i) => <path key={i} d={s.d} stroke={`url(#${s.grad})`} strokeWidth={s.width} style={{ opacity: s.opacity }} />)}</g>
          <g>{strands.mesh.map((s, i) => <path key={i} d={s.d} stroke={`url(#${s.grad})`} strokeWidth={s.width} style={{ opacity: s.opacity }} />)}</g>
        </svg>
      </div>
      <div className="lg-particles" aria-hidden="true">{Array.from({ length: 8 }, (_, i) => <span key={i} />)}</div>
      <div className="lg-visual" aria-hidden="true" />

      <section className="lg-wrap" aria-label="Sign in">
        <div className="lg-card">
          <header className="lg-brand"><div className="lg-logo"><img src={logo} alt="C5i" /></div></header>
          <p className="lg-title">Sign in to the Revenue Growth Simulator</p>
          <form onSubmit={submit} noValidate>
            <div className="lg-field"><div className="lg-shell">
              <svg className="lg-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" strokeWidth="1.7" /><path d="m4 7 8 6 8-6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg>
              <input ref={emailRef} type="email" name="email" autoComplete="username" aria-label="Email address" placeholder="Email address" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </div></div>
            <div className="lg-field"><div className="lg-shell">
              <svg className="lg-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="5" y="10" width="14" height="11" rx="2" stroke="currentColor" strokeWidth="1.7" /><path d="M8 10V7a4 4 0 0 1 8 0v3" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" /><path d="M12 14v3" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" /></svg>
              <input type={showPassword ? "text" : "password"} name="password" autoComplete="current-password" aria-label="Password" placeholder="Password" required value={password} onChange={(e) => setPassword(e.target.value)} />
              <button className="lg-toggle" type="button" aria-label={showPassword ? "Hide password" : "Show password"} title={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword((v) => !v)}>
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" aria-hidden="true"><path d="M2.5 12s3.4-6 9.5-6 9.5 6 9.5 6-3.4 6-9.5 6-9.5-6-9.5-6Z" stroke="currentColor" strokeWidth="1.7" /><circle cx="12" cy="12" r="2.8" stroke="currentColor" strokeWidth="1.7" /></svg>
              </button>
            </div></div>
            <div className="lg-options">
              <label className="lg-remember"><input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} /><span>Keep me signed in</span></label>
            </div>
            <button className="lg-submit" type="submit" disabled={busy}><span>Sign In</span><span className="lg-arrow" aria-hidden="true">→</span></button>
            <p className="lg-status" role="status" aria-live="polite">{status.text}</p>
          </form>
        </div>
      </section>
    </main></div>
  )
}
