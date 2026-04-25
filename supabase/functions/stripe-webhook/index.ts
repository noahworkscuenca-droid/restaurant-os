// Supabase Edge Function: stripe-webhook
// Deploy path: supabase/functions/stripe-webhook/index.ts
//
// Deploy command:
//   supabase functions deploy stripe-webhook --no-verify-jwt
//
// Set secrets:
//   supabase secrets set STRIPE_SECRET_KEY=sk_live_...
//   supabase secrets set STRIPE_WEBHOOK_SECRET=whsec_...
//   supabase secrets set STRIPE_PRICE_BASICO=price_...
//   supabase secrets set STRIPE_PRICE_PROFESIONAL=price_...
//   supabase secrets set STRIPE_PRICE_ENTERPRISE=price_...

import Stripe from "https://esm.sh/stripe@14.21.0?target=deno";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const stripe = new Stripe(Deno.env.get("STRIPE_SECRET_KEY")!, {
  apiVersion: "2024-04-10",
  httpClient: Stripe.createFetchHttpClient(),
});

const webhookSecret = Deno.env.get("STRIPE_WEBHOOK_SECRET")!;
const supabaseUrl   = Deno.env.get("SUPABASE_URL")!;
const supabaseKey   = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

// Map Stripe Price IDs to plan names
const PRICE_TO_PLAN: Record<string, string> = {
  [Deno.env.get("STRIPE_PRICE_BASICO")      ?? ""]: "basico",
  [Deno.env.get("STRIPE_PRICE_PROFESIONAL") ?? ""]: "profesional",
  [Deno.env.get("STRIPE_PRICE_ENTERPRISE")  ?? ""]: "enterprise",
};

Deno.serve(async (req: Request) => {
  const sig  = req.headers.get("stripe-signature");
  const body = await req.text();

  let event: Stripe.Event;
  try {
    event = await stripe.webhooks.constructEventAsync(body, sig!, webhookSecret);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error("Webhook signature error:", msg);
    return new Response("Webhook error: " + msg, { status: 400 });
  }

  const sb = createClient(supabaseUrl, supabaseKey);

  // Helper: update plan by stripe_customer_id
  async function updatePlan(
    customerId: string,
    subscriptionId: string,
    priceId: string,
    status: string,
  ) {
    const active = status === "active" || status === "trialing";
    const plan   = active ? (PRICE_TO_PLAN[priceId] ?? "free") : "free";
    const { error } = await sb.from("profiles").update({
      plan,
      stripe_subscription_id: subscriptionId,
    }).eq("stripe_customer_id", customerId);
    if (error) console.error("updatePlan error:", error);
    else console.log("Updated customer " + customerId + " to plan: " + plan);
  }

  // Helper: link Supabase user to Stripe customer
  async function linkCustomer(customerId: string, userId: string) {
    const { error } = await sb.from("profiles")
      .update({ stripe_customer_id: customerId })
      .eq("id", userId);
    if (error) console.error("linkCustomer error:", error);
  }

  // Event handling
  switch (event.type) {

    case "checkout.session.completed": {
      const session = event.data.object as Stripe.Checkout.Session;
      const userId  = session.metadata?.supabase_user_id;
      if (userId && session.customer) {
        await linkCustomer(session.customer as string, userId);
      }
      break;
    }

    case "customer.subscription.created":
    case "customer.subscription.updated": {
      const sub     = event.data.object as Stripe.Subscription;
      const priceId = sub.items.data[0]?.price.id ?? "";
      await updatePlan(
        sub.customer as string,
        sub.id,
        priceId,
        sub.status,
      );
      break;
    }

    case "customer.subscription.deleted": {
      const sub = event.data.object as Stripe.Subscription;
      await sb.from("profiles").update({
        plan: "free",
        stripe_subscription_id: null,
      }).eq("stripe_customer_id", sub.customer as string);
      break;
    }

    case "invoice.payment_succeeded": {
      const invoice = event.data.object as Stripe.Invoice;
      if (invoice.subscription && invoice.customer) {
        const sub = await stripe.subscriptions.retrieve(
          invoice.subscription as string,
        );
        const priceId = sub.items.data[0]?.price.id ?? "";
        await updatePlan(
          invoice.customer as string,
          sub.id,
          priceId,
          sub.status,
        );
      }
      break;
    }

    case "invoice.payment_failed": {
      console.warn("Payment failed for customer:", (event.data.object as Stripe.Invoice).customer);
      break;
    }

    default:
      console.log("Unhandled event type: " + event.type);
  }

  return new Response(JSON.stringify({ received: true }), {
    headers: { "Content-Type": "application/json" },
  });
});
