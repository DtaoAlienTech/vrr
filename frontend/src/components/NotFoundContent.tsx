import { LinkButton } from "@/components/ui/LinkButton";

export function NotFoundContent() {
  return (
    <section className="sec">
      <div className="wrap">
        <h1>Page not found</h1>
        <p className="lead">The page you are looking for does not exist or has moved.</p>
        <p className="mt-24">
          <LinkButton href="/">Go to the home page</LinkButton>
        </p>
      </div>
    </section>
  );
}
