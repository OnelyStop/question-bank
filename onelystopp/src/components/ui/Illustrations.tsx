export function HeroIllustration({ variant = "course" }: { variant?: "course" | "marker" | "diagram" | "interview" }) {
  if (variant === "marker") {
    return (
      <svg viewBox="0 0 280 260" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
        <rect x="48" y="36" width="170" height="190" rx="16" fill="#fff" stroke="#1a1a1f" strokeWidth="3" />
        <rect x="68" y="58" width="90" height="10" rx="5" fill="#5b52f0" />
        <rect x="68" y="82" width="130" height="8" rx="4" fill="#e8e8ec" />
        <rect x="68" y="100" width="118" height="8" rx="4" fill="#e8e8ec" />
        <rect x="68" y="118" width="124" height="8" rx="4" fill="#e8e8ec" />
        <rect x="68" y="148" width="70" height="28" rx="8" fill="#22a06b" />
        <text x="78" y="167" fill="#fff" fontSize="12" fontFamily="Plus Jakarta Sans, sans-serif" fontWeight="700">23/25</text>
        <circle cx="210" cy="56" r="22" fill="#f5c518" stroke="#1a1a1f" strokeWidth="3" />
        <path d="M202 56l5 5 11-12" stroke="#1a1a1f" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }

  if (variant === "diagram") {
    return (
      <svg viewBox="0 0 280 260" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
        <rect x="40" y="40" width="200" height="170" rx="16" fill="#f7f7f8" stroke="#1a1a1f" strokeWidth="3" />
        <circle cx="120" cy="120" r="42" fill="#2ec4b6" stroke="#1a1a1f" strokeWidth="3" />
        <circle cx="168" cy="120" r="42" fill="#f07167" stroke="#1a1a1f" strokeWidth="3" opacity="0.9" />
        <path d="M70 200 H210" stroke="#1a1a1f" strokeWidth="3" strokeLinecap="round" />
        <rect x="176" y="58" width="48" height="24" rx="8" fill="#5b52f0" />
        <text x="186" y="74" fill="#fff" fontSize="10" fontFamily="Plus Jakarta Sans, sans-serif" fontWeight="700">label</text>
      </svg>
    );
  }

  if (variant === "interview") {
    return (
      <svg viewBox="0 0 280 260" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
        <rect x="70" y="48" width="140" height="120" rx="20" fill="#fff" stroke="#1a1a1f" strokeWidth="3" />
        <circle cx="140" cy="98" r="28" fill="#eeedfe" stroke="#1a1a1f" strokeWidth="3" />
        <rect x="112" y="136" width="56" height="14" rx="7" fill="#5b52f0" />
        <rect x="100" y="188" width="16" height="36" rx="8" fill="#f5c518" stroke="#1a1a1f" strokeWidth="2.5" />
        <rect x="132" y="178" width="16" height="46" rx="8" fill="#5b52f0" stroke="#1a1a1f" strokeWidth="2.5" />
        <rect x="164" y="196" width="16" height="28" rx="8" fill="#f07167" stroke="#1a1a1f" strokeWidth="2.5" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 280 260" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
      <rect x="36" y="48" width="150" height="110" rx="14" fill="#fff" stroke="#1a1a1f" strokeWidth="3" />
      <rect x="52" y="66" width="70" height="10" rx="5" fill="#5b52f0" />
      <rect x="52" y="88" width="118" height="8" rx="4" fill="#e8e8ec" />
      <rect x="52" y="106" width="98" height="8" rx="4" fill="#e8e8ec" />
      <rect x="52" y="124" width="108" height="8" rx="4" fill="#e8e8ec" />
      <rect x="150" y="120" width="96" height="86" rx="14" fill="#f5c518" stroke="#1a1a1f" strokeWidth="3" />
      <text x="168" y="158" fill="#1a1a1f" fontSize="18" fontFamily="Plus Jakarta Sans, sans-serif" fontWeight="800">A*</text>
      <text x="164" y="182" fill="#1a1a1f" fontSize="11" fontFamily="Plus Jakarta Sans, sans-serif" fontWeight="700">ready</text>
      <circle cx="68" cy="196" r="26" fill="#f07167" stroke="#1a1a1f" strokeWidth="3" />
      <path d="M58 196h20M68 186v20" stroke="#fff" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function CertificateArt() {
  return (
    <svg viewBox="0 0 200 140" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
      <rect x="28" y="18" width="144" height="96" rx="10" fill="#fff" stroke="#d9d9e0" strokeWidth="2" />
      <rect x="48" y="38" width="70" height="8" rx="4" fill="#5b52f0" opacity="0.85" />
      <rect x="48" y="54" width="104" height="6" rx="3" fill="#e8e8ec" />
      <rect x="48" y="68" width="88" height="6" rx="3" fill="#e8e8ec" />
      <circle cx="140" cy="92" r="18" fill="#eeedfe" stroke="#5b52f0" strokeWidth="2" />
      <path d="M133 92l5 5 10-11" stroke="#5b52f0" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
      <rect x="86" y="104" width="28" height="18" rx="3" fill="#f5c518" stroke="#1a1a1f" strokeWidth="2" />
    </svg>
  );
}
