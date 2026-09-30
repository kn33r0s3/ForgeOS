import { createServerFn } from "@tanstack/react-start";
import { authMiddleware } from "@/lib/auth/middleware";
import { getSql } from "@/lib/db";
import {
  deleteUserPersonalContext,
  loadUserPersonalContext,
  saveUserPersonalContext,
} from "./personal-context-store";

export const getPersonalContext = createServerFn({ method: "GET" })
  .middleware([authMiddleware])
  .handler(async ({ context }) => {
    const sql = await getSql();
    return loadUserPersonalContext(sql, context.userId);
  });

export const savePersonalContext = createServerFn({ method: "POST" })
  .validator((input: unknown) => input)
  .middleware([authMiddleware])
  .handler(async ({ context, data }) => {
    const sql = await getSql();
    return saveUserPersonalContext(sql, context.userId, data);
  });

export const clearPersonalContext = createServerFn({ method: "POST" })
  .middleware([authMiddleware])
  .handler(async ({ context }) => {
    const sql = await getSql();
    await deleteUserPersonalContext(sql, context.userId);
    return { cleared: true };
  });
