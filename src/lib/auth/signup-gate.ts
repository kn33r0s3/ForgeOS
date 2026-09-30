import { createServerFn } from "@tanstack/react-start";

export const requestSignupPermit = createServerFn({ method: "POST" })
  .validator((input: unknown) => input)
  .handler(async ({ data }) => {
    const { requestSignupPermitOnServer } = await import("./signup-gate.server");
    return requestSignupPermitOnServer(data);
  });
