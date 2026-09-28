import { PublicClientApplication, type Configuration } from "@azure/msal-browser";

const clientId = import.meta.env.VITE_AZURE_CLIENT_ID || "";
const tenantId = import.meta.env.VITE_AZURE_TENANT_ID || "common";

export const isMsAuthEnabled = Boolean(clientId);

const msalConfig: Configuration = {
  auth: {
    clientId: clientId || "dummy-client-id",
    authority: `https://login.microsoftonline.com/${tenantId}`,
    redirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: "sessionStorage",
    storeAuthStateInCookie: false,
  },
};

let msalInstance: PublicClientApplication | null = null;

export async function getMsalInstance(): Promise<PublicClientApplication> {
  if (!msalInstance) {
    msalInstance = new PublicClientApplication(msalConfig);
    await msalInstance.initialize();
  }
  return msalInstance;
}

export async function loginWithMicrosoft(): Promise<string> {
  const instance = await getMsalInstance();
  const response = await instance.loginPopup({
    scopes: ["openid", "profile", "email"],
    prompt: "select_account",
  });
  return response.idToken;
}
