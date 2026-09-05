"use client";

import { createContext, useContext, useState, useEffect, type ReactNode } from "react";
import { api } from "@/lib/api";

interface DataSourceContextType {
  useLive: boolean;
  setUseLive: (v: boolean) => void;
  source: string;
  bayutConfigured: boolean;
}

const DataSourceContext = createContext<DataSourceContextType>({
  useLive: false,
  setUseLive: () => {},
  source: "mock",
  bayutConfigured: false,
});

export function DataSourceProvider({ children }: { children: ReactNode }) {
  const [useLive, setUseLive] = useState(false);
  const [source, setSource] = useState("mock");
  const [bayutConfigured, setBayutConfigured] = useState(false);

  useEffect(() => {
    api.getHealth().then((h) => {
      setSource(h.data_source);
      setBayutConfigured(h.bayut_configured);
    }).catch(() => {});
  }, []);

  return (
    <DataSourceContext.Provider value={{ useLive, setUseLive, source, bayutConfigured }}>
      {children}
    </DataSourceContext.Provider>
  );
}

export function useDataSource() {
  return useContext(DataSourceContext);
}
