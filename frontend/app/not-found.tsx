import Link from "next/link";

/**
 * Friendly fallback for a mistyped path. Worth having during a demo: the
 * default Next page gives no way back, and a URL with a stray character
 * pasted onto the end is an easy mistake to make.
 */
export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col items-center justify-center gap-6 px-6 text-center">
      <div className="space-y-2">
        <p className="text-sm font-medium uppercase tracking-widest text-slate-400">
          404
        </p>
        <h1 className="text-2xl font-bold text-slate-900">找不到這個頁面</h1>
        <p className="text-sm leading-relaxed text-slate-600">
          網址可能多了或少了字元。這個專案只有兩個頁面，請從下面選一個。
        </p>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row">
        <Link
          href="/"
          className="rounded-xl bg-sky-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-sky-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2"
        >
          消費者端（提出需求）
        </Link>
        <Link
          href="/vendor"
          className="rounded-xl border border-slate-300 px-5 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2"
        >
          廠商端（接案後台）
        </Link>
      </div>
    </main>
  );
}
