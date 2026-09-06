export function Reviews() {
  return (
    <section
      aria-labelledby="google-title"
      className="google-section wrap reputation-standalone"
      id="google-reviews"
    >
      <div className="review-story">
        <div className="google-intro">
          <span className="eyebrow">{"The perspective that matters"}</span>
          <h2 id="google-title">
            {"Their experience."}
            <br />
            {"Your confidence."}
          </h2>
          <p>
            {
              "Before you decide, hear from the people who have worked with Bali Zero."
            }
          </p>
          <a
            className="button"
            href="https://maps.app.goo.gl/whiMUTNchcDR5naz8"
            rel="noopener noreferrer"
            target="_blank"
          >
            {"Read our reviews on Google "}
            <span aria-hidden="true">{"↗"}</span>
          </a>
        </div>
        <figure className="adit-welcome">
          <img
            alt="Adit, Bali Zero Supervisor and Lead Setup, with a relaxed, welcoming smile."
            height="1537"
            loading="lazy"
            src="/assets/adit-site-bg.png"
            width="1023"
          />
          <figcaption>
            <strong>{"Adit"}</strong>
            <span>{"Supervisor · Lead Setup"}</span>
          </figcaption>
        </figure>
      </div>
      <div className="google-score">
        <span className="google-label">
          <svg
            aria-label="Google"
            height="28"
            role="img"
            viewBox="0 0 48 48"
            width="28"
          >
            <path
              d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z"
              fill="#4285F4"
            ></path>
            <path
              d="M6.306 14.691l6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 16.318 4 9.656 8.337 6.306 14.691z"
              fill="#34A853"
            ></path>
            <path
              d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238C29.211 35.091 26.715 36 24 36c-5.202 0-9.619-3.317-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44z"
              fill="#FBBC05"
            ></path>
            <path
              d="M43.611 20.083H42V20H24v8h11.303c-.792 2.237-2.231 4.166-4.087 5.571.001-.001.002-.001.003-.002l6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z"
              fill="#EA4335"
            ></path>
          </svg>
          <strong>{"Google Reviews"}</strong>
        </span>
        <p className="rating-count">Read our clients’ experiences.</p>
        <p className="rating-date">Latest ratings and feedback on Google.</p>
        <a
          className="textlink"
          href="https://maps.app.goo.gl/whiMUTNchcDR5naz8"
          rel="noopener noreferrer"
          target="_blank"
        >
          {"View the latest rating and reviews ↗"}
        </a>
      </div>
      <div className="google-detail">
        <p>{"Read the full story"}</p>
        <span>
          {
            "Explore individual reviews, dates and the latest feedback directly on Google."
          }
        </span>
        <a
          href="https://maps.app.goo.gl/whiMUTNchcDR5naz8"
          rel="noopener noreferrer"
          target="_blank"
        >
          {"Open Bali Zero on Google Maps ↗"}
        </a>
      </div>
    </section>
  );
}
