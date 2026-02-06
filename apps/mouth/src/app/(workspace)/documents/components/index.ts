/**
 * Documents Components Index
 * 
 * Esporta tutti i componenti della sezione documenti
 */

// Core Components
export { DriveBreadcrumb } from './DriveBreadcrumb';
export { DriveInfoPanel } from './DriveInfoPanel';
export { DriveSidebar } from './DriveSidebar';
export { DepartmentHome } from './DepartmentHome';

// Toolbar
export { DriveToolbar } from './DriveToolbar';
export { DriveToolbarOptimized } from './DriveToolbarOptimized';

// File Views
export { FileGrid } from './FileGrid';
export { FileGridVirtualized } from './FileGridVirtualized';
export { FileList } from './FileList';

// Skeletons
export { FileGridSkeleton } from './FileGridSkeleton';
export { FileListSkeleton } from './FileListSkeleton';

// Error Handling
export { 
  DocumentsErrorBoundary, 
  DocumentsInlineError 
} from './DocumentsErrorBoundary';

// Utilities
export { 
  getFileIcon, 
  getDepartmentInfo, 
  DEPARTMENT_COLORS 
} from './file-icon';
