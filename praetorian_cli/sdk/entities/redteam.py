class RedTeam:
    """
    Red Team operations entity for triggering terraform plan/apply and viewing history.
    """

    def __init__(self, api):
        self.api = api

    def plan(self) -> dict:
        """
        Trigger a terraform plan operation.

        Returns:
            dict: Response containing the plan operation status

        Example:
            >>> sdk.redteam.plan()
            {'message': 'Terraform plan triggered successfully', 'action': 'plan', 'status': 'initiated', ...}
        """
        return self.api.redteam_plan()

    def apply(self) -> dict:
        """
        Trigger a terraform apply operation.

        Returns:
            dict: Response containing the apply operation status

        Example:
            >>> sdk.redteam.apply()
            {'message': 'Terraform apply triggered successfully', 'action': 'apply', 'status': 'initiated', ...}
        """
        return self.api.redteam_apply()

    def launch(self, project_id: str) -> dict:
        """
        Trigger a red team operation launch.

        Args:
            project_id: GCP project ID for the red team engagement

        Returns:
            dict: Response containing the launch operation status

        Example:
            >>> sdk.redteam.launch('my-redteam-project')
            {'message': 'Red team launch triggered successfully', 'action': 'launch', 'status': 'initiated', ...}
        """
        return self.api.redteam_launch(project_id)

    def history(self) -> list:
        """
        Retrieve historical red team operation records.

        Returns:
            list: List of historical operation records

        Example:
            >>> sdk.redteam.history()
            [{'id': 'op-001', 'action': 'plan', 'status': 'completed', ...}, ...]
        """
        return self.api.redteam_history()
