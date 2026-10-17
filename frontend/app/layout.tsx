import type { Metadata } from 'next';
import './style.css';
export const metadata: Metadata = { title: 'Chai Animation Studio', description: 'Turn two-person dialogue audio into animated debate videos.' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
