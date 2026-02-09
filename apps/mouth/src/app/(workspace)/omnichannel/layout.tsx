import React from 'react';

export default function OmnichannelLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="h-[calc(100vh-64px)] w-full overflow-hidden bg-background">
      {/* 
        This layout removes the default padding often found in workspace layouts 
        to provide a true "Application" feel for the Command Center.
      */}
      {children}
    </div>
  );
}
