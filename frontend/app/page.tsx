import Link from "next/link";
import { ShieldCheck, Zap } from "lucide-react";

export default function LoginPage() {
  return (
    <main className="relative flex min-h-screen overflow-hidden bg-[#080808] text-white">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_40%,rgba(255,255,255,0.08),transparent_35%)]" />

      <div className="relative mx-auto grid min-h-screen w-full max-w-7xl lg:grid-cols-2">
        {/* LEFT */}
        <section className="hidden flex-col justify-between border-r border-white/10 p-10 lg:flex">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white text-black">
              <Zap size={18} fill="currentColor" />
            </div>

            <span className="font-black tracking-[0.25em]">
              ACR_AGENT
            </span>
          </div>

          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-white/30">
              Autonomous Code Repair
            </p>

            <h1 className="mt-6 text-7xl font-black leading-[0.85] tracking-[-0.06em]">
              CODE
              <br />
              FAILS.
              <br />
              AGENT
              <br />
              FIXES.
            </h1>

            <p className="mt-8 max-w-md text-sm leading-6 text-white/40">
              Analyze failures, generate repairs, validate changes and
              automate your GitHub workflow.
            </p>
          </div>

          <p className="text-xs text-white/20">
            AI + DEVOPS + DOCKER + GITHUB
          </p>
        </section>

        {/* LOGIN */}
        <section className="flex items-center justify-center p-6">
          <div className="w-full max-w-md">
            <div className="mb-10">
              <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 bg-white/5">
                <ShieldCheck size={26} />
              </div>

              <p className="text-xs uppercase tracking-[0.3em] text-white/30">
                Secure access
              </p>

              <h2 className="mt-3 text-4xl font-black tracking-tight">
                Welcome back.
              </h2>

              <p className="mt-3 text-sm text-white/40">
                Sign in to access your autonomous repair dashboard.
              </p>
            </div>

            <Link
              href="/auth"
              className="flex w-full items-center justify-center gap-3 rounded-2xl bg-white px-6 py-4 font-bold text-black transition hover:scale-[1.01]"
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  fill="#4285F4"
                  d="M21.35 12.23c0-.79-.07-1.55-.23-2.27H12v4.3h5.22a4.46 4.46 0 0 1-1.94 2.93v2.44h3.14c1.84-1.69 2.93-4.18 2.93-7.4Z"
                />
                <path
                  fill="#34A853"
                  d="M12 21.5c2.63 0 4.84-.87 6.45-2.37l-3.14-2.44c-.87.58-1.98.93-3.31.93-2.54 0-4.69-1.72-5.46-4.03H3.29v2.52A9.74 9.74 0 0 0 12 21.5Z"
                />
                <path
                  fill="#FBBC05"
                  d="M6.54 13.59A5.85 5.85 0 0 1 6.24 12c0-.55.1-1.09.3-1.59V7.89H3.29A9.73 9.73 0 0 0 2.25 12c0 1.57.38 3.05 1.04 4.11l3.25-2.52Z"
                />
                <path
                  fill="#EA4335"
                  d="M12 6.38c1.43 0 2.71.49 3.72 1.45l2.79-2.79C16.84 3.47 14.63 2.5 12 2.5a9.74 9.74 0 0 0-8.71 5.39l3.25 2.52C7.31 8.1 9.46 6.38 12 6.38Z"
                />
              </svg>

              Open sign in
            </Link>

            <div className="my-8 flex items-center gap-4">
              <div className="h-px flex-1 bg-white/10" />
              <span className="text-[10px] uppercase tracking-[0.25em] text-white/20">
                Protected
              </span>
              <div className="h-px flex-1 bg-white/10" />
            </div>

            <div className="grid grid-cols-3 gap-2 text-center text-[10px] uppercase tracking-wider text-white/25">
              <span className="rounded-xl border border-white/10 p-3">
                OAuth
              </span>
              <span className="rounded-xl border border-white/10 p-3">
                Session
              </span>
              <span className="rounded-xl border border-white/10 p-3">
                Secure
              </span>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
