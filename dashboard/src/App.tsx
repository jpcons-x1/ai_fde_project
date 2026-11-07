import { useEffect, useState } from "react";
import { api } from "./api";
import { ClaimPage } from "./ClaimPage";
import { useRoute } from "./hooks";
import { Instructions } from "./Instructions";
import { Queue } from "./Queue";

function Health() {
  const [status, setStatus] = useState("checking");

  useEffect(() => {
    void api
      .health()
      .then(() => "up")
      .catch(() => "down")
      .then(setStatus);
  }, []);

  return <span className="health">Backend: {status}</span>;
}

export function App() {
  const route = useRoute();

  return (
    <>
      <header className="header">
        <a className="brand" href="#/">
          <strong>UnderCover</strong>
          <span className="tagline">Claims desk</span>
        </a>
        <nav className="nav" aria-label="Main">
          <a
            href="#/"
            aria-current={route.page === "queue" ? "page" : undefined}
          >
            Queue
          </a>
          <a
            href="#/instructions"
            aria-current={route.page === "instructions" ? "page" : undefined}
          >
            Agent instructions
          </a>
        </nav>
        <Health />
      </header>
      <main className="page">
        {route.page === "queue" && <Queue />}
        {route.page === "claim" && (
          <ClaimPage key={route.claimId} claimId={route.claimId} />
        )}
        {route.page === "instructions" && <Instructions />}
      </main>
    </>
  );
}
