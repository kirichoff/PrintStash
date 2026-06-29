"use client";

import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

export function Checkbox({
  checked,
  onChange,
  className,
  ariaLabel,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  className?: string;
  ariaLabel?: string;
}) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      aria-label={ariaLabel}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        onChange(!checked);
      }}
      className={cn(
        "flex h-5 w-5 items-center justify-center rounded border transition-colors",
        checked
          ? "border-blue-600 bg-blue-600 text-white dark:border-orange-600 dark:bg-orange-600"
          : "border-border bg-background/80 text-transparent hover:border-blue-500 dark:hover:border-orange-500",
        className,
      )}
    >
      <Check className="h-3.5 w-3.5" strokeWidth={3} />
    </button>
  );
}
