const config = import.meta.env.PROD
  ? {
      apiBaseUrl: '/odossey_pos_kds',
    }
  : {
      apiBaseUrl: 'http://localhost:8070/odossey_pos_kds',
    }

export { config }
