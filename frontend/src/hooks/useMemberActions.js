import { useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";

/**
 * Encapsulates the three member-lifecycle actions (invite / create-direct /
 * remove) plus their loading + error state so `MemberList` can stay a pure
 * presentational orchestrator.
 */
export function useMemberActions({ onReload }) {
    const [inviting, setInviting] = useState(false);
    const [inviteError, setInviteError] = useState("");

    const [creatingUser, setCreatingUser] = useState(false);
    const [createUserErr, setCreateUserErr] = useState("");
    const [tempCreds, setTempCreds] = useState(null);

    const invite = async ({ email, role, department }) => {
        setInviteError("");
        setInviting(true);
        try {
            await api.post("/enterprise/organizations/invites", {
                email, role, department: department || null,
            });
            onReload();
            return true;
        } catch (e) {
            setInviteError(e.response?.data?.detail || "Invite failed");
            return false;
        } finally {
            setInviting(false);
        }
    };

    const createUserDirect = async ({ email, full_name, department, role }) => {
        setCreateUserErr("");
        setCreatingUser(true);
        try {
            const res = await api.post("/enterprise/organizations/users", {
                email, full_name, department: department || null, role,
            });
            setTempCreds({
                email: res.data.user.email,
                temp_password: res.data.temp_password,
                name: res.data.user.full_name,
            });
            onReload();
            return true;
        } catch (e) {
            setCreateUserErr(e.response?.data?.detail || "Create failed");
            return false;
        } finally {
            setCreatingUser(false);
        }
    };

    const removeMember = async (memberId) => {
        if (!window.confirm("Remove this team member?")) return;
        try {
            await api.delete(`/enterprise/organizations/members/${memberId}`);
            onReload();
        } catch (e) {
            toast.error(e.response?.data?.detail || "Failed");
        }
    };

    return {
        invite, inviting, inviteError,
        createUserDirect, creatingUser, createUserErr,
        tempCreds, clearTempCreds: () => setTempCreds(null),
        removeMember,
    };
}
