import "./globals.css";

type PageMetadata = {
  title: string;
  description: string;
};

export const metadata: PageMetadata = {
  title: "Tìm kiếm tin tức tiếng Việt",
  description: "Giao diện tìm kiếm tin tức tiếng Việt với gợi ý, bộ lọc và kết quả rõ ràng hơn.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
