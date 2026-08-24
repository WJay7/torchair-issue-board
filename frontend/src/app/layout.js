import "./globals.css";

export const metadata = {
  title: "TorchAir issue",
  description: "TorchAir issue 看板",
  icons: {
    icon: "/torchair-logo.png",
    apple: "/torchair-logo.png",
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
