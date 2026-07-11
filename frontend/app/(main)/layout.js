'use client';

import { useSidebar } from '../../hooks/useSidebar';
import Sidebar from '../../components/Sidebar';

export default function MainLayout({ children }) {
  const { isSidebarCollapsed, canAnimate } = useSidebar();

  return (
    <div className={`container ${isSidebarCollapsed ? 'sidebar-collapsed' : ''}${!canAnimate ? ' no-animate' : ''}`}>
      <Sidebar />
      {children}
    </div>
  );
}
