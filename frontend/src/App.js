import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import "@/App.css";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import Header from "@/components/layout/Header";
import Footer from "@/components/layout/Footer";
import AITutorPanel from "@/components/AITutorPanel";
import ProtectedRoute from "@/components/ProtectedRoute";

import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import ForgotPassword from "@/pages/ForgotPassword";
import ResetPassword from "@/pages/ResetPassword";
import AuthCallback from "@/pages/AuthCallback";
import CourseCatalog from "@/pages/CourseCatalog";
import CourseDetail from "@/pages/CourseDetail";
import LessonViewer from "@/pages/LessonViewer";
import Dashboard from "@/pages/Dashboard";
import Quiz from "@/pages/Quiz";
import Certificate from "@/pages/Certificate";
import Verify from "@/pages/Verify";
import Industries from "@/pages/Industries";
import Enterprise from "@/pages/Enterprise";
import Certifications from "@/pages/Certifications";
import Pricing from "@/pages/Pricing";
import Intelligence from "@/pages/Intelligence";
import CheckoutSuccess from "@/pages/CheckoutSuccess";
import EnterprisePortal from "@/pages/EnterprisePortal";
import EnterpriseSetup from "@/pages/EnterpriseSetup";
import EnterpriseJoin from "@/pages/EnterpriseJoin";
import Mentor from "@/pages/Mentor";
import Paths from "@/pages/Paths";
import PathDetail from "@/pages/PathDetail";
import Passport from "@/pages/Passport";
import PatchReview from "@/pages/PatchReview";
import Trust from "@/pages/Trust";
import Podcast from "@/pages/Podcast";
import SuperAdminPortal from "@/pages/SuperAdminPortal";
import LegalDoc from "@/pages/LegalDoc";

function AppShell() {
    const location = useLocation();
    const { user } = useAuth();

    // Detect OAuth callback synchronously
    if (location.hash?.includes("session_id=")) {
        return <AuthCallback />;
    }

    // Hide chrome on lesson viewer for immersive reading
    const isLesson = location.pathname.startsWith("/learn/");

    return (
        <div className="min-h-screen flex flex-col">
            <Header />
            <main className="flex-1">
                <Routes>
                    <Route path="/" element={<Landing />} />
                    <Route path="/login" element={<Login />} />
                    <Route path="/register" element={<Register />} />
                    <Route path="/forgot-password" element={<ForgotPassword />} />
                    <Route path="/reset-password" element={<ResetPassword />} />
                    <Route path="/courses" element={<CourseCatalog />} />
                    <Route path="/courses/:slug" element={<CourseDetail />} />
                    <Route path="/industries" element={<Industries />} />
                    <Route path="/certifications" element={<Certifications />} />
                    <Route path="/pricing" element={<Pricing />} />
                    <Route path="/pricing/success" element={<ProtectedRoute><CheckoutSuccess /></ProtectedRoute>} />
                    <Route path="/intelligence" element={<Intelligence />} />
                    <Route path="/enterprise" element={<Enterprise />} />
                    <Route path="/verify" element={<Verify />} />
                    <Route path="/verify/:certId" element={<Verify />} />
                    <Route path="/trust" element={<Trust />} />
                    <Route path="/podcast" element={<Podcast />} />

                    <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
                    <Route path="/mentor" element={<ProtectedRoute><Mentor /></ProtectedRoute>} />
                    <Route path="/paths" element={<Paths />} />
                    <Route path="/paths/:slug" element={<PathDetail />} />
                    <Route path="/passport" element={<ProtectedRoute><Passport /></ProtectedRoute>} />
                    <Route path="/passport/:slug" element={<Passport />} />
                    <Route path="/patches" element={<ProtectedRoute><PatchReview /></ProtectedRoute>} />
                    <Route path="/learn/:slug/:moduleId/:lessonId" element={<ProtectedRoute><LessonViewer /></ProtectedRoute>} />
                    <Route path="/quiz/:slug" element={<ProtectedRoute><Quiz /></ProtectedRoute>} />
                    <Route path="/certificate/:certId" element={<ProtectedRoute><Certificate /></ProtectedRoute>} />
                    <Route path="/enterprise/portal" element={<ProtectedRoute><EnterprisePortal /></ProtectedRoute>} />
                    <Route path="/enterprise/setup" element={<ProtectedRoute><EnterpriseSetup /></ProtectedRoute>} />
                    <Route path="/enterprise/join" element={<ProtectedRoute><EnterpriseJoin /></ProtectedRoute>} />
                    {/* Super-admin console — deliberately unlinked from public nav. */}
                    <Route path="/admin" element={<ProtectedRoute><SuperAdminPortal /></ProtectedRoute>} />
                    {/* Legal & compliance pages */}
                    <Route path="/legal/disclaimer" element={<LegalDoc docKey="disclaimer" />} />
                    <Route path="/legal/terms" element={<LegalDoc docKey="terms" />} />
                    <Route path="/legal/security" element={<LegalDoc docKey="security" />} />
                    <Route path="/legal/compliance" element={<LegalDoc docKey="compliance" />} />
                </Routes>
            </main>
            {!isLesson && <Footer />}
            {user && <AITutorPanel courseSlug={location.pathname.startsWith("/learn/") ? location.pathname.split("/")[2] : null} />}
        </div>
    );
}

function App() {
    return (
        <div className="App">
            <BrowserRouter>
                <AuthProvider>
                    <AppShell />
                </AuthProvider>
            </BrowserRouter>
        </div>
    );
}

export default App;
