import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";

export const useServerHealth = () => {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => api.getHealth(),
    staleTime: 1000 * 60
  });
};
