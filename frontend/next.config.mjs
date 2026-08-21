/** @type {import('next').NextConfig} */
const isGithubPages = process.env.GITHUB_ACTIONS === "true";

const nextConfig = {
  output: "export",
  images: { unoptimized: true },
  basePath: isGithubPages ? "/torchair-issue-board" : "",
};

export default nextConfig;
