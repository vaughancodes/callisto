import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";
import { VoicemailsList } from "../components/VoicemailsList";
import { useDocumentTitle } from "../hooks/useDocumentTitle";

export function VoicemailsPage() {
  useDocumentTitle("Voicemails");
  return (
    <div className="p-4 sm:p-6 max-w-4xl">
      <div className="flex items-center gap-3 mb-6">
        <Link
          to="/"
          aria-label="Back to dashboard"
          className="p-2 hover:bg-page-hover rounded-lg transition-colors"
        >
          <ArrowLeft className="w-5 h-5 text-page-text" />
        </Link>
        <h2 className="text-2xl font-bold text-page-text">Voicemails</h2>
      </div>
      <VoicemailsList variant="page" />
    </div>
  );
}
