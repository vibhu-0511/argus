const url = process.env.ARGUS_APP_URL;
if (!url) {
  process.exit(2);
}
const response = await fetch(url);
process.exit(response.ok ? 0 : 1);
