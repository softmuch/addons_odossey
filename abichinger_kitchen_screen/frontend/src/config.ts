const config = import.meta.env.PROD
  ? {
      apiBaseUrl: '/abichinger_kitchen_screen',
    }
  : {
      apiBaseUrl: 'http://localhost:8070/abichinger_kitchen_screen',
    }

export { config }
