import net from "node:net";

const socket = net.connect({ host: "1.1.1.1", port: 443 });
const timer = setTimeout(() => {
  socket.destroy();
  process.exit(1);
}, 3000);
socket.on("connect", () => {
  clearTimeout(timer);
  process.exit(0);
});
socket.on("error", () => {
  clearTimeout(timer);
  process.exit(1);
});
