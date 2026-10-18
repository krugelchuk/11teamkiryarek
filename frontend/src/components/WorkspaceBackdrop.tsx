import './WorkspaceBackdrop.css';

/** Decorative type only. It cannot capture clicks, focus or screen-reader output. */
export default function WorkspaceBackdrop() {
  return <div className="workspace-backdrop" aria-hidden="true">
    <span className="workspace-backdrop-glow" />
    <span className="workspace-backdrop-word">JANA</span>
  </div>;
}
