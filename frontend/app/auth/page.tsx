"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import {
    ArrowRight,
    Check,
    Eye,
    EyeOff,
    Chrome,
    LockKeyhole,
    Mail,
    ShieldCheck,
    Sparkles,
    UserRound,
    Workflow,
    Zap,
} from "lucide-react";

type AuthMode = "login" | "signup";
const API_URL = process.env.NEXT_PUBLIC_ACR_API_URL || "http://localhost:8000";

const benefits = [
    "Private release intelligence for your team",
    "Automatic failure triage and healing trails",
    "One calm command center for every deployment",
];

export default function AuthPage() {
    const [mode, setMode] = useState<AuthMode>("login");
    const [showPassword, setShowPassword] = useState(false);
    const [remember, setRemember] = useState(true);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const isSignup = mode === "signup";

    useEffect(() => {
        const error = new URLSearchParams(window.location.search).get("oauth_error");
        if (error) {
            toast.error("Google sign-in failed", { description: error });
            window.history.replaceState({}, document.title, "/auth");
        }
    }, []);

    const switchMode = (nextMode: AuthMode) => {
        setMode(nextMode);
        setShowPassword(false);
    };

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        setIsSubmitting(true);
        const form = new FormData(event.currentTarget);
        try {
            const response = await fetch(`${API_URL}/auth/${isSignup ? "signup" : "login"}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({
                    name: String(form.get("name") || ""),
                    email: String(form.get("email") || ""),
                    password: String(form.get("password") || ""),
                    remember,
                }),
            });
            const body = await response.json() as { user?: { name?: string }; detail?: string };
            if (!response.ok) {
                throw new Error(body.detail || "Authentication failed.");
            }
            setIsSubmitting(false);
            toast.success(isSignup ? "Account created" : "Signed in", {
                description: `Welcome ${body.user?.name || "to ACR Agent"}.`,
            });
            window.location.assign("/dashboard");
        } catch (error) {
            setIsSubmitting(false);
            toast.error(error instanceof Error ? error.message : "Authentication failed", {
                description: "Confirm the backend is running on port 8000.",
            });
        }
    };

    return (
        <main className="auth-page">
            <div className="auth-backdrop" />
            <div className="auth-grid" />
            <div className="auth-scanline" />

            <header className="auth-header">
                <Link className="auth-brand" href="/" aria-label="ACR Agent home">
                    <span className="auth-brand-mark">
                        <span>A</span>
                        <Sparkles aria-hidden="true" />
                    </span>
                    <span>
                        <strong>ACR <em>AGENT</em></strong>
                        <small>AUTONOMOUS CODE RECOVERY</small>
                    </span>
                </Link>
                <div className="auth-header-status">
                    <span className="auth-status-dot" />
                    ENCRYPTED SESSION
                </div>
            </header>

            <section className="auth-shell">
                <div className="auth-story">
                    <div className="auth-kicker"><Workflow aria-hidden="true" /> RELEASE INTELLIGENCE, ACTIVATED</div>
                    <h1>Ship with a system that <span>sees the failure coming.</span></h1>
                    <p className="auth-story-copy">
                        ACR Agent turns noisy CI failures into a clean path forward, so your team can spend its energy on the next breakthrough.
                    </p>

                    <div className="auth-benefits">
                        {benefits.map((benefit) => (
                            <div className="auth-benefit" key={benefit}>
                                <span><Check aria-hidden="true" /></span>
                                <p>{benefit}</p>
                            </div>
                        ))}
                    </div>

                    <div className="auth-signal">
                        <div className="auth-signal-icon"><Zap aria-hidden="true" /></div>
                        <div>
                            <strong>THE RECOVERY FABRIC IS ONLINE</strong>
                            <p>Ready to make your next release uneventful.</p>
                        </div>
                        <span className="auth-signal-line" />
                    </div>
                </div>

                <div className="auth-card">
                    <div className="auth-card-topline"><span /> NODE ACCESS / 01</div>
                    <div className="auth-card-heading">
                        <div>
                            <p className="auth-eyebrow">{isSignup ? "CREATE YOUR COMMAND CENTER" : "WELCOME BACK, OPERATOR"}</p>
                            <h2>{isSignup ? "Build your edge." : "Resume control."}</h2>
                        </div>
                        <div className="auth-lock"><LockKeyhole aria-hidden="true" /></div>
                    </div>

                    <div className="auth-mode-switch" role="tablist" aria-label="Authentication mode">
                        <button className={mode === "login" ? "active" : ""} onClick={() => switchMode("login")} role="tab" aria-selected={mode === "login"} type="button">Sign in</button>
                        <button className={mode === "signup" ? "active" : ""} onClick={() => switchMode("signup")} role="tab" aria-selected={mode === "signup"} type="button">Create account</button>
                    </div>

                    <form className="auth-form" onSubmit={handleSubmit}>
                        {isSignup && (
                            <label className="auth-field">
                                <span>FULL NAME</span>
                                <div className="auth-input-wrap">
                                    <UserRound aria-hidden="true" />
                                    <input name="name" type="text" placeholder="Alex Morgan" autoComplete="name" required />
                                </div>
                            </label>
                        )}

                        <label className="auth-field">
                            <span>WORK EMAIL</span>
                            <div className="auth-input-wrap">
                                <Mail aria-hidden="true" />
                                <input name="email" type="email" placeholder="you@company.com" autoComplete="email" required />
                            </div>
                        </label>

                        <label className="auth-field">
                            <span>ACCESS KEY</span>
                            <div className="auth-input-wrap">
                                <LockKeyhole aria-hidden="true" />
                                <input name="password" type={showPassword ? "text" : "password"} placeholder="Enter your password" autoComplete={isSignup ? "new-password" : "current-password"} minLength={8} required />
                                <button className="auth-password-toggle" type="button" onClick={() => setShowPassword((visible) => !visible)} aria-label={showPassword ? "Hide password" : "Show password"}>
                                    {showPassword ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
                                </button>
                            </div>
                        </label>

                        {isSignup ? (
                            <label className="auth-check auth-terms">
                                <input type="checkbox" required />
                                <span>I agree to the <a href="#terms">operator terms</a> and privacy protocol.</span>
                            </label>
                        ) : (
                            <div className="auth-form-options">
                                <label className="auth-check">
                                    <input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} />
                                    <span>Keep me connected</span>
                                </label>
                                <button type="button" className="auth-text-button" onClick={() => toast.info("Recovery link requested", { description: "Check your inbox for the next step." })}>Forgot access?</button>
                            </div>
                        )}

                        <button className="auth-submit" disabled={isSubmitting} type="submit">
                            <span>{isSubmitting ? "VERIFYING..." : isSignup ? "INITIALIZE WORKSPACE" : "ENTER ACR AGENT"}</span>
                            {!isSubmitting && <ArrowRight aria-hidden="true" />}
                        </button>
                    </form>

                    <div className="auth-divider"><span>OR CONTINUE WITH</span></div>
                    <button className="auth-github" type="button" onClick={() => window.location.assign(`${API_URL}/auth/google/start`)}>
                        <Chrome aria-hidden="true" /> Continue with Google
                    </button>

                    <p className="auth-footnote">
                        <ShieldCheck aria-hidden="true" /> Your workspace data stays yours, always.
                    </p>
                </div>
            </section>

            <footer className="auth-footer">
                <span>ACR / SECURE ACCESS LAYER</span>
                <span>BUILD 0.9.7 <i /> ALL SYSTEMS NOMINAL</span>
            </footer>
        </main>
    );
}
