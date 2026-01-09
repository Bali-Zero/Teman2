'use client';

import Image from 'next/image';

export interface UserAvatarProps {
  userName: string;
  userAvatar: string | null;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizeConfig = {
  sm: { classes: 'w-8 h-8', dimensions: 32 },
  md: { classes: 'w-9 h-9', dimensions: 36 },
  lg: { classes: 'w-12 h-12', dimensions: 48 },
};

/**
 * User avatar display component with fallback initials
 */
export function UserAvatar({ userName, userAvatar, size = 'sm', className = '' }: UserAvatarProps) {
  const config = sizeConfig[size];

  if (userAvatar) {
    return (
      <Image
        src={userAvatar}
        alt="User"
        width={config.dimensions}
        height={config.dimensions}
        className={`${config.classes} rounded-full object-cover ${className}`}
      />
    );
  }

  return (
    <div className={`${config.classes} rounded-full bg-[#2a2a2a] flex items-center justify-center ${className}`}>
      <span className="text-gray-300 font-medium text-sm">
        {userName ? userName.substring(0, 2).toUpperCase() : 'U'}
      </span>
    </div>
  );
}
