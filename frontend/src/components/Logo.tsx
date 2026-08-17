import React from "react";
import Image from "next/image";
import { EnvironmentBadge } from "./EnvironmentBadge";

/**
 * Sidebar wordmark. Swap /public/logo.png to rebrand; width/height are the
 * asset's intrinsic 845x295 and only fix the aspect ratio.
 */
const Logo: React.FC = () => {
  return (
    <div className="mb-2 flex items-center gap-2">
      <Image
        src="/logo.png"
        alt="Providend Meeting Assistant"
        width={845}
        height={295}
        priority
        className="h-auto w-40"
      />
      <EnvironmentBadge />
    </div>
  );
};

Logo.displayName = "Logo";

export default Logo;
