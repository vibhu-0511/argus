import { createRoot } from "react-dom/client";

// One host for each flow in config/platform.md: sign-in, ops menu, desk, user admin, audit.
function Flows() {
  return (
    <>
      <div id="sign-in">Sign in</div>
      <button id="ops-menu" type="button">
        Ops menu
      </button>
      <div id="desk">Desk</div>
      <span id="user-admin">User admin</span>
      <span id="audit">Audit</span>
    </>
  );
}

const root = document.getElementById("root");
if (!root) throw new Error("root missing");
createRoot(root).render(<Flows />);
