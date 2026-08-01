/**
 * Decorative backdrop for the resident-facing page, tuned to read as part of
 * the 統一集團 ecosystem: warm red-orange washes plus a sparse pattern of the
 * group's business lines (food and beverage, convenience retail, logistics,
 * home services).
 *
 * Everything here is drawn by hand. It deliberately does NOT reproduce the
 * group's registered logo or 7-ELEVEN's mark -- that needs the official asset
 * and permission to use it. Drop such a file in as an <img> inside
 * `BrandStrip` below if you have both.
 *
 * Kept very pale on purpose: white cards sit on top of it and their text has to
 * stay at full contrast.
 */
export default function BrandBackdrop() {
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      {/* Warm base wash: stronger at the corners so the middle stays readable. */}
      <div className="absolute inset-0 bg-[radial-gradient(70rem_50rem_at_88%_-12%,rgb(252_165_165/0.5),transparent_58%),radial-gradient(58rem_48rem_at_-12%_2%,rgb(253_186_116/0.45),transparent_56%),radial-gradient(60rem_45rem_at_18%_112%,rgb(254_202_202/0.5),transparent_58%),radial-gradient(50rem_40rem_at_95%_105%,rgb(254_215_170/0.4),transparent_58%)]" />

      {/* Business-line motifs, tiled. Sparse enough to read as texture. */}
      <svg className="absolute inset-0 h-full w-full text-rose-900/[0.04]">
        <defs>
          <pattern
            id="uni-motifs"
            width="208"
            height="208"
            patternUnits="userSpaceOnUse"
          >
            <g
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              {/* Beverage cup: food and drinks. */}
              <path d="M18 24h20l-2.2 21a3 3 0 0 1-3 2.7h-9.6a3 3 0 0 1-3-2.7z" />
              <path d="M16.5 24h23" />
              <path d="M28 18v-4" />

              {/* Shopping basket: convenience retail. */}
              <path d="M96 30h26l-3 17a2.6 2.6 0 0 1-2.6 2.2h-14.8A2.6 2.6 0 0 1 99 47z" />
              <path d="M103 30l3-7h6l3 7" />

              {/* Logistics carton. */}
              <path d="M22 106h26v20H22z" />
              <path d="M22 112h26" />
              <path d="M33 106v6" />

              {/* Home services: a roof with a spark. */}
              <path d="M98 120l13-11 13 11" />
              <path d="M101.5 122v12h19v-12" />
              <path d="M111 125.5l1.4 3.1 3.1 1.4-3.1 1.4-1.4 3.1-1.4-3.1-3.1-1.4 3.1-1.4z" />
            </g>
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#uni-motifs)" />
      </svg>

      {/* A single oversized "U" as a quiet anchor, bottom-right. */}
      <svg
        viewBox="0 0 200 200"
        className="absolute -bottom-16 -right-10 h-[26rem] w-[26rem] text-rose-800/[0.045]"
      >
        <path
          d="M52 38v72a48 48 0 0 0 96 0V38"
          fill="none"
          stroke="currentColor"
          strokeWidth="15"
          strokeLinecap="round"
        />
      </svg>
    </div>
  );
}

/**
 * The line that names the sponsor. Text only, so it carries no trademark.
 * Replace the text node with the official logo asset if you have clearance.
 */
export function BrandStrip() {
  return (
    <p className="flex items-center gap-2 text-[11px] text-slate-500">
      <span
        aria-hidden="true"
        className="h-3.5 w-1 rounded-full bg-gradient-to-b from-red-500 to-orange-400"
      />
      統一集團 × 智慧社區生活服務
    </p>
  );
}
