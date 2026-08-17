'use client';

import React from 'react';

interface MainContentProps {
  children: React.ReactNode;
}

const MainContent: React.FC<MainContentProps> = ({ children }) => {
  return (
    // ml-64 matches the fixed sidebar width
    <main className="flex-1 ml-64">
      <div className="pl-8">
        {children}
      </div>
    </main>
  );
};

export default MainContent;
