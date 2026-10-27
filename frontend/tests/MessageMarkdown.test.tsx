import React from "react";
import { afterEach, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MessageMarkdown } from "../src/components/MessageMarkdown";

afterEach(cleanup);

it("renders rich Markdown including GFM tables and task lists", () => {
  const { container } = render(
    <MessageMarkdown
      content={[
        "## Services",
        "",
        "**SEO** and *advertising*, with ~~old pricing~~.",
        "",
        "1. Audit",
        "2. Optimize",
        "   - Local listings",
        "",
        "> Based on your documents.",
        "",
        "| Service | Price |",
        "| --- | ---: |",
        "| SEO | $100 |",
        "",
        "- [x] Audit complete",
        "- [ ] Follow up",
        "",
        "Use `npm run dev`.",
        "",
        "```js",
        "const price = 100;",
        "```",
        "",
        "[Contact](https://example.com)",
      ].join("\n")}
    />,
  );
  expect(screen.getByRole("heading", { level: 2 }).textContent).toBe(
    "Services",
  );
  expect(container.querySelector("strong")?.textContent).toBe("SEO");
  expect(container.querySelector("em")?.textContent).toBe("advertising");
  expect(container.querySelector("del")?.textContent).toBe("old pricing");
  expect(container.querySelector("ol ul li")?.textContent).toBe(
    "Local listings",
  );
  expect(container.querySelector("blockquote")?.textContent).toContain(
    "Based on your documents.",
  );
  expect(screen.getByRole("table").textContent).toContain("$100");
  expect(screen.getByRole("region", { name: "Response table" }).tabIndex).toBe(
    0,
  );
  const tasks = screen.getAllByRole("checkbox") as HTMLInputElement[];
  expect(tasks.map((task) => task.checked)).toEqual([true, false]);
  expect(tasks.every((task) => task.disabled)).toBe(true);
  expect(
    container.querySelector("pre code.language-js")?.textContent,
  ).toContain("const price = 100;");
  expect(
    screen.getByRole("link", { name: "Contact" }).getAttribute("rel"),
  ).toBe("noopener noreferrer");
});

it("does not execute raw HTML, render remote images, or expose javascript links", () => {
  const { container } = render(
    <MessageMarkdown
      content={
        '<script>alert(1)</script>\n\n<img src="https://example.com/tracker">\n\n![tracker](https://example.com/image.png)\n\n[unsafe](javascript:alert%281%29)'
      }
    />,
  );
  expect(container.querySelector("script, img")).toBeNull();
  expect(screen.getByText("unsafe").getAttribute("href") || "").not.toContain(
    "javascript:",
  );
});

it("handles an unfinished streamed code fence and its completed response", () => {
  const { container, rerender } = render(
    <MessageMarkdown content={'```python\nprint("Hi")'} />,
  );
  expect(container.querySelector("pre code")?.textContent).toContain(
    'print("Hi")',
  );
  rerender(
    <MessageMarkdown content={'```python\nprint("Hi")\n```\n\n**Done**'} />,
  );
  expect(container.querySelector("strong")?.textContent).toBe("Done");
});
