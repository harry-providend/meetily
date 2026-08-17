import React from "react";
import Image from "next/image";

/**
 * Sidebar wordmark. Swap /public/logo.png to change the brand image --
 * width/height below are the current asset's intrinsic size (845x295) and
 * only set the aspect ratio; rendered width comes from the className.
 */
const Logo: React.FC = () => {
  return (
    <div className="mb-2 flex items-center">
      <Image
        src="/logo.png"
        alt="Providend Meeting Assistant"
        width={845}
        height={295}
        priority
        className="h-auto w-40"
      />
    </div>
  );
};

Logo.displayName = "Logo";

export default Logo;
