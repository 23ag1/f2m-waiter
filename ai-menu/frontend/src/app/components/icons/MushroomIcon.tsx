interface MushroomIconProps {
  className?: string;
  size?: number;
}

export default function MushroomIcon({ className = '', size = 24 }: MushroomIconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      {/* Mushroom cap */}
      <path d="M12 3C7.5 3 4 6.5 4 10.5C4 12 4.5 13 5.5 13.5H18.5C19.5 13 20 12 20 10.5C20 6.5 16.5 3 12 3Z" />
      {/* Spots on cap */}
      <circle cx="9" cy="9" r="1" fill="currentColor" />
      <circle cx="15" cy="9" r="1" fill="currentColor" />
      <circle cx="12" cy="7" r="1" fill="currentColor" />
      {/* Mushroom stem */}
      <path d="M10 13.5V20C10 20.5 10.5 21 11 21H13C13.5 21 14 20.5 14 20V13.5" />
      {/* Gills under cap */}
      <line x1="8" y1="13" x2="8" y2="14" />
      <line x1="10" y1="13" x2="10" y2="14" />
      <line x1="12" y1="13" x2="12" y2="14" />
      <line x1="14" y1="13" x2="14" y2="14" />
      <line x1="16" y1="13" x2="16" y2="14" />
    </svg>
  );
}
