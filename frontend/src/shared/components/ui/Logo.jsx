const Logo = ({ size = 40 }) => (
  <svg width={size} height={size} viewBox="0 0 40 40" fill="none">
    <rect x="4" y="4" width="18" height="32" rx="1" fill="#291100" />
    <rect x="8" y="8" width="8" height="12" rx="0" fill="#FBF2DA" />
    <rect x="16" y="8" width="4" height="12" rx="8" fill="#291100" />
    <polygon points="10,36 14,24 18,36" fill="#291100" />
    <polygon points="12,35 14,28 16,35" fill="#FBF2DA" />
    <circle cx="14" cy="38" r="2" fill="#8B0000" />
  </svg>
);

export default Logo;
