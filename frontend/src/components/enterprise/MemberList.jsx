import { useState } from "react";
import { useMemberActions } from "@/hooks/useMemberActions";
import MembersTable from "./MembersTable";
import InviteForm from "./InviteForm";
import CreateUserModal from "./CreateUserModal";
import TempCredsModal from "./TempCredsModal";

/**
 * Members section for the Enterprise portal. Orchestrates the members table,
 * invite form, direct-create modal, and temp-creds reveal. Business logic
 * lives in `useMemberActions`; each UI concern is its own component.
 */
export default function MemberList({ dashboard, isAdmin, onReload }) {
    const { organization: org, summary, members } = dashboard;
    const [showCreateUser, setShowCreateUser] = useState(false);

    const actions = useMemberActions({ onReload });

    return (
        <>
            <div className="flex items-center justify-between mb-4">
                <h2 className="font-serif text-2xl tracking-tight">Team members</h2>
                <span className="text-xs font-mono uppercase tracking-[0.15em] text-muted-foreground">
                    {summary.seats_used}/{summary.seat_count} seats
                </span>
            </div>

            <MembersTable members={members} isAdmin={isAdmin} onRemove={actions.removeMember} />

            {isAdmin && showCreateUser && (
                <CreateUserModal
                    org={org}
                    onClose={() => setShowCreateUser(false)}
                    onSubmit={actions.createUserDirect}
                    err={actions.createUserErr}
                    loading={actions.creatingUser}
                    seatsRemaining={summary.seats_remaining}
                />
            )}

            {actions.tempCreds && (
                <TempCredsModal creds={actions.tempCreds} onClose={actions.clearTempCreds} />
            )}

            {isAdmin && (
                <InviteForm
                    seatsRemaining={summary.seats_remaining}
                    onInvite={actions.invite}
                    inviting={actions.inviting}
                    inviteError={actions.inviteError}
                    onOpenCreateUser={() => setShowCreateUser(true)}
                />
            )}
        </>
    );
}
