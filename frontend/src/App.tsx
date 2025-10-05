import { Route, Routes } from "react-router-dom";

import { AppLayout } from "./components/AppLayout";
import { CampaignDetailPage } from "./pages/CampaignDetailPage";
import { CampaignListPage } from "./pages/CampaignListPage";

const App = () => {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<CampaignListPage />} />
        <Route path="/campaigns/:campaignId" element={<CampaignDetailPage />} />
      </Routes>
    </AppLayout>
  );
};

export default App;
